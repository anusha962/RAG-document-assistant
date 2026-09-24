from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Document

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "chunk_count", "created_at"]


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class ChatSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)
    document_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    history = serializers.ListField(child=serializers.DictField(), required=False)
