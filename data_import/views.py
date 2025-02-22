import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView

from data_import.models import StandardizedFile, RespondingAgency, Upload
from data_import.utils import ChildEmployerQueue, ParentEmployerQueue, \
    RespondingAgencyQueue

from payroll.models import Employer


class Uploads(LoginRequiredMixin, ListView):
    '''
    Index of data import. Display a list of standardized uploads,
    their statuses, and next steps.
    '''
    template_name = 'data_import/index.html'
    model = Upload
    context_object_name = 'uploads'
    paginate_by = 10

    def get_queryset(self):
        return Upload.objects.filter(standardized_file__isnull=False)\
                             .order_by('-created_at')


class Review(LoginRequiredMixin, DetailView):
    template_name = 'data_import/review.html'

    @property
    def change_url(self):
        return reverse(
            'admin:data_import_standardizedfile_change',
            args=(self.kwargs['s_file_id'],)
        )

    def dispatch(self, request, *args, **kwargs):
        if self.request.GET.get('flush') == 'true':
            self.q.flush()
            messages.info(self.request, 'Remaining items are being added to the database.')

        # TODO: This may be redundant with render_to_response, but I'll keep it
        # here protectively.
        if self.q.remaining == 0:
            self.finish_review_step()
            return redirect(self.change_url)

        else:
            return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        '''
        If nothing is available for checkout, finish the review step.
        '''
        if context['object']:
            return super().render_to_response(context, **response_kwargs)

        else:
            self.finish_review_step()
            messages.info(self.request, 'All items have been reviewed.')
            return redirect(self.change_url)

    def get_object(self):
        item_id, item = self.q.checkout()

        if item:
            item['id'] = item_id.decode('utf-8')
            return item

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'entity': self.entity,
            'entities': self.entities,
            's_file_id': self.kwargs['s_file_id'],
            'remaining': self.q.remaining,
        })

        return context

    def finish_review_step(self):
        s_file = StandardizedFile.objects.get(id=self.kwargs['s_file_id'])
        getattr(s_file, self.transition)()


class RespondingAgencyReview(Review):
    transition = 'select_unseen_parent_employer'
    entity = 'responding agency'
    entities = 'responding agencies'

    @property
    def q(self):
        return RespondingAgencyQueue(self.kwargs['s_file_id'])


class ParentEmployerReview(Review):
    transition = 'select_unseen_child_employer'
    entity = 'parent employer'
    entities = 'parent employers'

    @property
    def q(self):
        return ParentEmployerQueue(self.kwargs['s_file_id'])


class ChildEmployerReview(Review):
    transition = 'insert_salaries'
    entity = 'child employer'
    entities = 'child employers'

    @property
    def q(self):
        return ChildEmployerQueue(self.kwargs['s_file_id'])


@login_required
def review(request):
    '''
    Both /match/ and /add/ resolve here.
    '''
    data = json.loads(request.POST['data'])

    entity_type = data['entity_type']
    s_file_id = data['s_file_id']
    unseen = data['unseen']
    match = data.get('match')  # None if adding

    if 'match' in request.build_absolute_uri('?'):
        assert match
    else:
        assert not match

    q_map = {
        'responding-agency': RespondingAgencyQueue,
        'parent-employer': ParentEmployerQueue,
        'child-employer': ChildEmployerQueue,
    }

    q = q_map[entity_type](s_file_id)
    q.match_or_create(unseen, match)

    return JsonResponse({'status_code': 200})


@login_required
def review_entity_lookup(request, entity_type):
    q = request.GET['term']

    queryset_map = {
        'responding-agency': RespondingAgency.objects,
        'parent-employer': Employer.objects.filter(parent_id__isnull=True),
        'child-employer': Employer.objects.filter(parent_id__isnull=False),
    }

    queryset = queryset_map[entity_type]

    entities = []

    for e in queryset.filter(name__istartswith=q):
        data = {
            'label': str(e),
            'value': e.id,
        }
        entities.append(data)

    return JsonResponse(entities, safe=False)
