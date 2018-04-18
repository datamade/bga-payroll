import datetime
import json

from django.http import HttpResponse
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView

from data_import.forms import UploadForm
from data_import.models import SourceFile, StandardizedFile, RespondingAgency, \
    Upload
from data_import.tasks import copy_to_database


class SourceFileHook(View):
    def post(self, request):
        '''
        Accept post containing file metadata & ID in Google Drive
        '''
        upload = Upload.objects.create()
        source_files = json.loads(request.POST['source_files'])

        for file_metadata in source_files:
            agency = file_metadata.pop('responding_agency')
            responding_agency, _ = RespondingAgency.objects.get_or_create(name=agency)

            file_metadata['upload'] = upload
            file_metadata['responding_agency'] = responding_agency

            file_metadata = self._hydrate_date_objects(file_metadata)

            SourceFile.objects.create(**file_metadata)

        # TO-DO: Kick off delayed task, which iterates over all source files
        # without an attached file and calls SourceFile.download_from_drive

        return HttpResponse('Caught!')

    def _hydrate_date_objects(self, file_metadata):
        '''
        Convert date strings to Python date objects.
        '''
        date_fields = [k for k in file_metadata.keys() if k.endswith('date')]

        for field in date_fields:
            date_string = file_metadata[field]
            date_object = datetime.datetime.strptime(date_string, '%Y-%m-%d')
            file_metadata[field] = date_object

        return file_metadata


class StandardizedDataUpload(FormView):
    template_name = 'data_import/upload.html'
    form_class = UploadForm
    success_url = 'upload-success/'

    def form_valid(self, form):
        upload = Upload.objects.create()

        uploaded_file = form.cleaned_data['standardized_file']
        now = datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S')
        uploaded_file.name = '{}-{}'.format(now, uploaded_file.name)

        s_file_meta = {
            'standardized_file': uploaded_file,
            'upload': upload,
            'reporting_year': form.cleaned_data['reporting_year'],
        }

        s_file = StandardizedFile.objects.create(**s_file_meta)

        copy_to_database.delay(s_file_id=s_file.id)

        return super().form_valid(form)


class Uploads(ListView):
    '''
    Index of data import. Display a list of standardized uploads,
    their statuses, and next steps.
    '''
    template_name = 'data_import/index.html'
    model = Upload
    context_object_name = 'uploads'

    def get_queryset(self):
        return Upload.objects.filter(standardized_file__isnull=False)
