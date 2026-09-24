import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import rag
from .models import Document
from .serializers import ChatSerializer, DocumentSerializer, RegisterSerializer, UploadSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User.objects.create_user(**s.validated_data)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username}, status=status.HTTP_201_CREATED)


class LoginView(ObtainAuthToken):
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        s = self.serializer_class(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class DocumentViewSet(
    mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def get_throttles(self):
        self.throttle_scope = "upload" if self.action == "create" else None
        return super().get_throttles()

    def create(self, request):
        s = UploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        upload = s.validated_data["file"]
        if upload.size > settings.MAX_UPLOAD_BYTES:
            return Response({"detail": "That file is larger than 10 MB."}, status=400)
        try:
            doc = rag.ingest(request.user, upload)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        except Exception as e:
            logger.exception("Ingestion failed")
            detail = "Couldn't process this file. Check that it has selectable text and try again."
            if settings.DEBUG:  # local development: show the real reason
                detail = f"Upload failed: {type(e).__name__}: {str(e)[:200]}"
            return Response({"detail": detail}, status=502)
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class ChatView(APIView):
    throttle_scope = "chat"

    def post(self, request):
        s = ChatSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            result = rag.answer(request.user, d["question"], d.get("document_ids"), d.get("history"))
        except Exception:
            logger.exception("Chat failed")
            return Response({"detail": "The AI service didn't respond. Please try again."}, status=502)
        return Response(result)


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatStreamView(APIView):
    """Server-sent events: `sources` first, then `token` events, then `done`."""

    throttle_scope = "chat"

    def post(self, request):
        s = ChatSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        def events():
            try:
                messages, sources = rag.prepare(
                    request.user, d["question"], d.get("document_ids"), d.get("history")
                )
                yield _sse("sources", sources)
                if not messages:
                    yield _sse("token", "There's nothing to search yet. Upload a document first.")
                elif not rag.has_llm():
                    yield _sse("token", rag.offline_answer(sources))
                else:
                    for piece in rag.stream_generate(rag.SYSTEM_PROMPT, messages):
                        yield _sse("token", piece)
                yield _sse("done", {})
            except Exception:
                logger.exception("Chat stream failed")
                yield _sse("error", "The AI service didn't respond. Please try again.")

        resp = StreamingHttpResponse(events(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp
