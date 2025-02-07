from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView

app_name = 'luapol_app'

urlpatterns = [
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),  # Redirect root URL to login
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('verification-pending/<int:user_id>/', views.verification_pending_view, name='verification_pending'),
    path('verify-email/<int:user_id>/<str:token>/', views.activate_account_view, name='verify_email'),
    path('chat/', views.chat_view, name='chat'),
    path('result/<int:test_id>/', views.test_detail_view, name='detalle_test'),
    path('start/', views.start_view, name='start'),
    path('test/<str:test_id>/', views.test_detail_view, name='test_detail'), 
    path('test_save_remaining_time/<str:test_id>/', views.test_save_remaining_time_view, name='test_save_remaining_time'),
    path('confirm_test/<str:test_id>/', views.confirm_test_view, name='confirm_test'),
    path('test/<str:test_id>/finalize/', views.finalize_test_view, name='finalize_test'),
    path('my_profile/', views.profile_view, name='my_profile'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('change_password/', views.change_password_view, name='change_password'),
    path('edit_profile/', views.edit_profile_view, name='edit_profile'),
    path('privacy_policy/', views.privacy_policy_view, name='privacy_policy'),
    path('delete_event/', views.delete_event_view, name='delete_event'),
    path('event_list/', views.event_list_view, name='event_list'),
    path('test/<str:test_id>/analysis', views.test_analysis_view, name='test_analysis'),
    path('create_block/', views.create_block_view, name='create_block'),
    path('complete_review/<str:test_id>/', views.complete_review_view, name='complete_review'),
    path('new_block/', views.new_block_view, name='new_block'),
    path('favoritas/', views.preguntas_favoritas_view, name='preguntas_favoritas'),
    path('pregunta/<str:pregunta_test_id>/favorita/', views.toggle_favorita, name='toggle_favorita'),
    path('test/<str:test_id>/start/', views.test_start_view, name='test_start'),
    path('test/<str:test_id>/review/', views.test_detail_review_view, name='test_detail_review'),
    path('forum/', views.forum_list_view, name='forum_list'), 
    path('forum/topic/<str:entrada_id>/', views.forum_detail_view, name='forum_detail'), 
    path('forum/new_pregunta/', views.forum_newPregunta_view, name='forum_new_pregunta'),
    path('forum/new_general/', views.forum_newGeneral_view, name='forum_new_general'),
    path('forum/entries/', views.forum_entries_for_question, name='forum_entries_for_question'),
    path('forum_megusta/<str:object_type>/<str:object_id>/', views.toggle_forum_megusta_view, name='toggle_megusta'),
    path('delete_blocks/', views.delete_blocks_view, name='delete_blocks'),
    path('reports/average_attempts/', views.average_attempts_view, name='average_attempts'),
    path('reports/general_progress/', views.general_progress_view, name='general_progress'),
    path('reports/user_ranking/', views.user_ranking_view, name='user_ranking'),
    path('reports/', views.list_reports_view, name='list_reports'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/check/', views.check_notifications, name='check_notifications'),
    path('notifications/<str:notification_id>/detail/', views.notification_detail, name='notification_detail'),
]
