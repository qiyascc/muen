from rest_framework import generics, status
from rest_framework.response import Response
from .models import Config
from .serializers import ConfigSerializer, BrandsSerializer


class ConfigBrandsAPIView(generics.RetrieveAPIView):
    """
    API view to retrieve brands from the Config model.
    This endpoint returns the brands field of the first Config object in the database.
    If no Config object exists, it returns an empty list.
    """
    serializer_class = BrandsSerializer
    
    def get_object(self):
        """
        Get the first Config object or create a default one if none exists.
        """
        config, created = Config.objects.get_or_create(
            name='default',
            defaults={'brands': []}
        )
        return config
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the brands field and return it directly.
        """
        instance = self.get_object()
        return Response({'brands': instance.brands})
