import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'snack.settings')
from django.core.asgi import get_asgi_application
django_application = get_asgi_application()
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from chat.consumers import ChatConsumer
application = ProtocolTypeRouter({'http': django_application, 'websocket': AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter([path('ws/workspaces/<int:workspace_id>/', ChatConsumer.as_asgi())])))})
