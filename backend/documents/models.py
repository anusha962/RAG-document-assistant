from django.conf import settings
from django.db import models


class Document(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    chunk_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField()
    page = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    embedding = models.BinaryField()  # float32 unit vector

    class Meta:
        ordering = ["document_id", "index"]
