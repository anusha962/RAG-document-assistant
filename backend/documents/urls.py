from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChatStreamView, ChatView, DocumentViewSet, LoginView, RegisterView

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("chat/", ChatView.as_view()),
    path("chat/stream/", ChatStreamView.as_view()),
    path("", include(router.urls)),
]
