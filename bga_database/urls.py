"""bga_database URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views.decorators.cache import cache_page

from data_import import views as import_views
from payroll import views as payroll_views


urlpatterns = [
    # client
    path('', cache_page(60 * 15)(payroll_views.IndexView.as_view()), name='home'),
    path('user-guide/', payroll_views.UserGuideView.as_view(), name='user_guide'),
    path('unit/<str:slug>/', cache_page(60 * 15)(payroll_views.UnitView.as_view()), name='unit'),
    path('department/<str:slug>/', cache_page(60 * 15)(payroll_views.DepartmentView.as_view()), name='department'),
    path('person/<str:slug>/', cache_page(60 * 15)(payroll_views.PersonView.as_view()), name='person'),
    path('entity-lookup/', payroll_views.EntityLookup.as_view(), name='entity-lookup'),
    path('search/', payroll_views.SearchView.as_view(), name='search'),
    path('<int:error_code>', payroll_views.error, name='error'),

    # admin
    path('admin/', admin.site.urls),
    path('flush-cache/<str:secret_key>', payroll_views.flush_cache, name='flush_cache'),

    # data import
    path('data-import/', import_views.Uploads.as_view(), name='data-import'),
    path('data-import/upload-source-file/', import_views.SourceFileHook.as_view(), name='upload-source-file'),
    path('data-import/upload-standardized-file/', import_views.StandardizedDataUpload.as_view(), name='upload-standardized-file'),
    path('data-import/review/responding-agency/<int:s_file_id>', import_views.RespondingAgencyReview.as_view(), name='review-responding-agency'),
    path('data-import/review/parent-employer/<int:s_file_id>', import_views.ParentEmployerReview.as_view(), name='review-parent-employer'),
    path('data-import/review/child-employer/<int:s_file_id>', import_views.ChildEmployerReview.as_view(), name='review-child-employer'),
    path('data-import/lookup/<str:entity_type>/', import_views.review_entity_lookup, name='review-entity-lookup'),
    path('data-import/match/', import_views.review, name='match-entity'),
    path('data-import/add/', import_views.review, name='add-entity'),
]


if settings.DEBUG:
    from django.conf.urls import include, url
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    import debug_toolbar

    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

    urlpatterns += staticfiles_urlpatterns()

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
