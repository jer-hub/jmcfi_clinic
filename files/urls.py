from django.urls import path

from . import views

app_name = 'files'

urlpatterns = [
    path('', views.drive_browse, name='browse'),
    path('trash/', views.drive_trash, name='trash'),
    path('trash/empty/', views.trash_empty, name='trash_empty'),
    path('trash/bulk-restore/', views.trash_bulk_restore, name='trash_bulk_restore'),
    path('trash/bulk-purge/', views.trash_bulk_purge, name='trash_bulk_purge'),
    path('search/', views.drive_search, name='search'),
    path('folder/create/', views.folder_create, name='folder_create'),
    path('upload/', views.drive_upload, name='upload'),
    path('bulk-trash/', views.drive_bulk_trash, name='bulk_trash'),
    path('<int:pk>/download/', views.drive_download, name='download'),
    path('<int:pk>/rename/', views.item_rename, name='rename'),
    path('<int:pk>/move/', views.item_move, name='move'),
    path('<int:pk>/trash/', views.item_trash, name='item_trash'),
    path('<int:pk>/restore/', views.item_restore, name='restore'),
    path('<int:pk>/purge/', views.item_purge, name='purge'),
]
