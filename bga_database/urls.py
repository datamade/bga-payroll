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
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.decorators.cache import cache_page

from data_import import views as import_views
from payroll import views as payroll_views
from payroll import api as api_views
from payroll import sitemaps as payroll_sitemaps

from rest_framework import routers


router = routers.DefaultRouter()
router.register(r'index', api_views.IndexViewSet, 'index')
router.register(r'units', api_views.UnitViewSet)
router.register(r'departments', api_views.DepartmentViewSet)
router.register(r'people', api_views.PersonViewSet)

EIGHT_HOURS = 60 * 60 * 8

sitemaps = {
    'units': payroll_sitemaps.UnitSitemap,
    'departments': payroll_sitemaps.DepartmentSitemap,
}

urlpatterns = [
    # client
    path('', cache_page(EIGHT_HOURS)(payroll_views.IndexView.as_view()), name='home'),
    path('user-guide/', cache_page(EIGHT_HOURS)(payroll_views.UserGuideView.as_view()), name='user_guide'),
    path('unit/<str:slug>/', cache_page(EIGHT_HOURS)(payroll_views.UnitView.as_view()), name='unit'),
    path('department/<str:slug>/', cache_page(EIGHT_HOURS)(payroll_views.DepartmentView.as_view()), name='department'),
    path('person/<str:slug>/', cache_page(EIGHT_HOURS)(payroll_views.PersonView.as_view()), name='person'),
    path('entity-lookup/', payroll_views.EntityLookup.as_view(), name='entity-lookup'),
    path('search/', payroll_views.SearchView.as_view(), name='search'),
    path('story-feed/', payroll_views.StoryFeed.as_view(), name='story-feed'),
    path('<int:error_code>', payroll_views.error, name='error'),

    # user auth
    path('salsa/', include('salsa_auth.urls')),

    # admin
    path('admin/', admin.site.urls),
    path('flush-cache/<str:secret_key>', payroll_views.flush_cache, name='flush_cache'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # data import
    path('data-import/', import_views.Uploads.as_view(), name='data-import'),
    path('data-import/review/responding-agency/<int:s_file_id>', import_views.RespondingAgencyReview.as_view(), name='review-responding-agency'),
    path('data-import/review/parent-employer/<int:s_file_id>', import_views.ParentEmployerReview.as_view(), name='review-parent-employer'),
    path('data-import/review/child-employer/<int:s_file_id>', import_views.ChildEmployerReview.as_view(), name='review-child-employer'),
    path('data-import/lookup/<str:entity_type>/', import_views.review_entity_lookup, name='review-entity-lookup'),
    path('data-import/match/', import_views.review, name='match-entity'),
    path('data-import/add/', import_views.review, name='add-entity'),
]

urlpatterns += [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
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
