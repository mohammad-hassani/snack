from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from chat import views, api_views
from chat.forms import LoginForm
urlpatterns = [
    path('api/session/', api_views.session),
    path('api/auth/login/', api_views.sign_in),
    path('api/auth/signup/', api_views.sign_up),
    path('api/auth/logout/', api_views.sign_out),
    path('api/auth/password-reset/', api_views.password_reset),
    path('api/auth/reset/<str:uidb64>/<str:token>/', api_views.password_confirm),
    path('api/workspaces/', api_views.workspaces),
    path('api/invites/<uuid:token>/', api_views.invitation),
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/login/', auth_views.LoginView.as_view(authentication_form=LoginForm), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('workspaces/create/', views.create_workspace, name='create_workspace'),
    path('invite/<uuid:token>/', views.accept_invite, name='accept_invite'),
    path('files/<int:attachment_id>/', views.download),
    path('health/', views.health),
    path('api/workspaces/<int:workspace_id>/', views.bootstrap),
    path('api/workspaces/<int:workspace_id>/channels/', views.create_channel),
    path('api/workspaces/<int:workspace_id>/direct/', views.direct_message),
    path('api/workspaces/<int:workspace_id>/search/', views.search),
    path('api/workspaces/<int:workspace_id>/invites/', views.invite),
    path('api/workspaces/<int:workspace_id>/members/<int:user_id>/', views.manage_member),
    path('api/channels/<int:channel_id>/messages/', views.channel_messages),
    path('api/channels/<int:channel_id>/read/', views.read_channel),
    path('api/messages/<int:message_id>/', views.message_detail),
]
