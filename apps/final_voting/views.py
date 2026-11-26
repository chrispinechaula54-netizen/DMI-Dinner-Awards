import csv
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Election, BallotCategory, BallotDivision, Candidate, Ballot, VoteSelection, VotingAudit
from .services import category_complete, category_ready, published_categories


@login_required
def ballot_view(request):
    election = Election.current()
    if election.status != 'open':
        return render(request, 'voting/closed.html', {'election': election})
    existing = Ballot.objects.filter(voter=request.user).first()
    if existing and not election.allow_ballot_edits:
        return render(request, 'voting/already_voted.html', {'ballot': existing})
    categories = published_categories()
    selected = {s.division_id: s.candidate_id for s in existing.selections.all()} if existing else {}
    return render(request, 'voting/ballot.html', {'categories': categories, 'selected': selected, 'election': election})


@login_required
@require_POST
def submit_ballot(request):
    election = Election.current()
    if election.status != 'open':
        messages.error(request, 'Voting is closed. Your ballot was not recorded.')
        return redirect('final_voting:ballot')
    categories = published_categories()
    divisions = [d for c in categories for d in c.divisions.all()]
    submitted = {}
    for division in divisions:
        value = request.POST.get(f'division_{division.pk}')
        if not value:
            messages.error(request, f'Please make one selection for {division}.')
            return redirect('final_voting:ballot')
        candidate = division.candidates.filter(pk=value, confirmed=True).first() if str(value).isdigit() else None
        if not candidate:
            messages.error(request, 'One or more selections are not valid for this ballot.')
            return redirect('final_voting:ballot')
        submitted[division.pk] = candidate
    if not divisions:
        messages.error(request, 'The approved ballot is not ready yet.')
        return redirect('final_voting:ballot')
    try:
        with transaction.atomic():
            ballot = Ballot.objects.select_for_update().filter(voter=request.user).first()
            if ballot and not election.allow_ballot_edits:
                messages.error(request, 'Your final voting ballot has already been recorded.')
                return redirect('final_voting:ballot')
            if ballot:
                ballot.selections.all().delete()
            else:
                ballot = Ballot.objects.create(voter=request.user)
            VoteSelection.objects.bulk_create([VoteSelection(ballot=ballot, division_id=key, candidate=value) for key, value in submitted.items()])
    except IntegrityError:
        messages.error(request, 'Your final voting ballot has already been recorded.')
        return redirect('final_voting:ballot')
    return render(request, 'voting/thank_you.html', {'ballot': ballot})


@staff_member_required
def manage_view(request):
    election = Election.current()
    categories = BallotCategory.objects.prefetch_related('divisions__candidates').order_by('display_order')
    readiness = {category.pk: category_complete(category) for category in categories}
    ready_to_approve = sum(readiness[c.pk] and not c.approved for c in categories)
    ballots_exist = Ballot.objects.exists()
    can_approve_all = election.status != 'closed' and bool(ready_to_approve) and (not ballots_exist or election.allow_ballot_edits)
    return render(request, 'voting/manage.html', {'election': election, 'categories': categories, 'readiness': readiness, 'ballots_exist': ballots_exist, 'ready_to_approve': ready_to_approve, 'can_approve_all': can_approve_all})


@staff_member_required
@require_POST
def manage_action(request):
    election = Election.current()
    action = request.POST.get('action')
    candidate_id = request.POST.get('candidate_id')
    category_id = request.POST.get('category_id')
    division_id = request.POST.get('division_id')
    detail = ''
    if action == 'candidate_save':
        candidate = get_object_or_404(Candidate, pk=candidate_id) if candidate_id else None
        division = candidate.division if candidate else get_object_or_404(BallotDivision, pk=division_id)
        if (election.status == 'open' and division.category.approved) or (candidate and candidate.selections.exists()):
            messages.error(request, 'Candidates on a published category or recorded vote cannot be changed.')
            return redirect('final_voting:manage')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Candidate name is required.')
        else:
            if candidate is None:
                candidate = Candidate(division=division, position=(division.candidates.order_by('-position').values_list('position', flat=True).first() or 0) + 1)
            candidate.name = name
            candidate.confirmed = request.POST.get('confirmed') == 'on'
            candidate.save()
            detail = f'{action}: {candidate.name}'
    elif action == 'candidate_delete':
        candidate = get_object_or_404(Candidate, pk=candidate_id)
        if (election.status == 'open' and candidate.division.category.approved) or candidate.selections.exists():
            messages.error(request, 'Candidates on a published category or recorded vote cannot be removed.')
            return redirect('final_voting:manage')
        detail = f'Removed candidate {candidate.name}'
        candidate.delete()
    elif action == 'category_approve':
        if election.status == 'closed' or (Ballot.objects.exists() and not election.allow_ballot_edits):
            messages.error(request, 'Categories cannot be approved after voting closes or when recorded ballots are locked.')
            return redirect('final_voting:manage')
        category = get_object_or_404(BallotCategory, pk=category_id)
        if category_ready_without_approval(category):
            category.approved = True
            category.save(update_fields=['approved'])
            detail = f'Approved category {category.name}'
        else:
            messages.error(request, 'Category cannot be approved until all required candidates are confirmed and complete.')
    elif action == 'approve_all':
        ballots_exist = Ballot.objects.exists()
        if election.status == 'closed' or (ballots_exist and not election.allow_ballot_edits):
            messages.error(request, 'Bulk approval is unavailable after voting closes or when recorded ballots are locked.')
            return redirect('final_voting:manage')
        candidates = list(BallotCategory.objects.filter(method='online').order_by('display_order'))
        complete = [category for category in candidates if category_complete(category)]
        if not complete:
            messages.error(request, 'There are no complete online categories to approve yet.')
            return redirect('final_voting:manage')
        BallotCategory.objects.filter(pk__in=[category.pk for category in complete]).update(approved=True)
        newly_approved = sum(not category.approved for category in complete)
        detail = f'Approved {newly_approved} complete online categories in bulk.'
    elif action == 'toggle_edits':
        election.allow_ballot_edits = request.POST.get('enabled') == 'true'
        election.save(update_fields=['allow_ballot_edits'])
        detail = f'Ballot edit policy set to {election.allow_ballot_edits}'
    elif action in ('draft', 'ready', 'open', 'close', 'reopen'):
        if action in ('ready', 'open', 'reopen'):
            invalid = [c.name for c in BallotCategory.objects.filter(method='online') if c.approved and not category_ready(c)]
            if invalid:
                messages.error(request, 'Approved ballot includes incomplete categories: ' + ', '.join(invalid))
                return redirect('final_voting:manage')
        if action == 'ready':
            if not BallotCategory.objects.filter(method='online', approved=True).exists():
                messages.error(request, 'Approve at least one complete category before marking the ballot ready.')
                return redirect('final_voting:manage')
            election.status = 'ready'
        elif action in ('open', 'reopen'):
            if action == 'open' and election.status != 'ready':
                messages.error(request, 'Move the election to Ready for approval before opening it. Use Reopen for a closed election.')
                return redirect('final_voting:manage')
            if action == 'reopen' and election.status != 'closed':
                messages.error(request, 'Only a closed election can be reopened.')
                return redirect('final_voting:manage')
            if action == 'reopen' and request.POST.get('confirm_reopen') != 'yes':
                messages.error(request, 'Reopening voting requires explicit confirmation.')
                return redirect('final_voting:manage')
            if action == 'open' and not BallotCategory.objects.filter(method='online', approved=True).exists():
                messages.error(request, 'Approve at least one complete category before opening voting.')
                return redirect('final_voting:manage')
            election.status, election.opened_at = 'open', timezone.now()
            election.approved_by, election.approved_at = request.user, timezone.now()
        elif action in ('close',): election.status, election.closed_at = 'closed', timezone.now()
        else: election.status = 'draft'
        election.save()
        detail = f'Election status changed to {election.status}'
    if detail:
        VotingAudit.objects.create(actor=request.user, action=action.upper(), details=detail)
        if action == 'approve_all' and Ballot.objects.exists():
            messages.warning(request, f'{detail} Existing voters can revisit their ballots to add selections for the newly approved categories.')
        elif action == 'approve_all':
            messages.success(request, f'{detail} Incomplete categories remain unpublished.')
        else:
            messages.success(request, 'Final voting management updated.')
    return redirect('final_voting:manage')


def category_ready_without_approval(category):
    category.approved = True
    try:
        return category_ready(category)
    finally:
        category.approved = False


@staff_member_required
def results_view(request):
    categories = BallotCategory.objects.filter(method='online', approved=True).prefetch_related('divisions__candidates').order_by('display_order')
    for category in categories:
        category.total_votes = 0
        for division in category.divisions.all():
            division.result_candidates = list(division.candidates.annotate(vote_count=Count('selections')).order_by('-vote_count', 'position'))
            division.total_votes = sum(candidate.vote_count for candidate in division.result_candidates)
            category.total_votes += division.total_votes
            last_votes, rank = None, 0
            for index, candidate in enumerate(division.result_candidates, 1):
                if candidate.vote_count != last_votes:
                    rank = index
                    last_votes = candidate.vote_count
                candidate.rank = rank
    from django.contrib.auth import get_user_model
    total_voters = get_user_model().objects.filter(is_active=True, is_staff=False).count()
    ballot_count = Ballot.objects.count()
    dinner = BallotCategory.objects.filter(method='dinner').prefetch_related('divisions__candidates').first()
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="final_voting_results.csv"'
        writer = csv.writer(response)
        writer.writerow(['Category', 'Division', 'Candidate or pair', 'Votes'])
        for category in categories:
            for division in category.divisions.all():
                for candidate in division.candidates.annotate(vote_count=Count('selections')).order_by('-vote_count'):
                    writer.writerow([category.name, division.label, candidate.name, candidate.vote_count])
        return response
    return render(request, 'voting/results.html', {'categories': categories, 'total_voters': total_voters, 'ballot_count': ballot_count, 'participation': round(100 * ballot_count / total_voters, 1) if total_voters else 0, 'dinner': dinner, 'audit': VotingAudit.objects.select_related('actor')[:25]})


@staff_member_required
def preview_view(request):
    categories = [c for c in BallotCategory.objects.filter(method='online').prefetch_related('divisions__candidates').order_by('display_order') if category_complete(c)]
    return render(request, 'voting/ballot.html', {'categories': categories, 'selected': {}, 'election': Election.current(), 'preview': True})


@staff_member_required
@require_POST
def dinner_result(request):
    candidate = get_object_or_404(Candidate, pk=request.POST.get('candidate_id'), division__category__method='dinner')
    Candidate.objects.filter(division__category=candidate.division.category).update(dinner_result=False, winner_confirmed=False)
    candidate.dinner_result = True
    candidate.winner_confirmed = request.POST.get('confirm') == 'on'
    candidate.save(update_fields=['dinner_result', 'winner_confirmed'])
    VotingAudit.objects.create(actor=request.user, action='DINNER_RESULT_RECORDED', details=f'{candidate.division.category.name}: {candidate.name}; confirmed={candidate.winner_confirmed}')
    return redirect('final_voting:results')


@staff_member_required
@require_POST
def confirm_winner(request):
    if Election.current().status != 'closed':
        messages.error(request, 'Close voting before confirming winners.')
        return redirect('final_voting:results')
    candidate = get_object_or_404(Candidate, pk=request.POST.get('candidate_id'), division__category__method='online')
    candidate.winner_confirmed = request.POST.get('confirm') == 'on'
    candidate.save(update_fields=['winner_confirmed'])
    VotingAudit.objects.create(actor=request.user, action='WINNER_CONFIRMATION_CHANGED', details=f'{candidate.division.category.name} / {candidate.division.label}: {candidate.name}; confirmed={candidate.winner_confirmed}')
    return redirect('final_voting:results')
