from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command
from apps.awards.models import AwardCategory
from apps.nominations.models import Nomination, NominationDraft
from .models import Election, BallotCategory, BallotDivision, Candidate, Ballot, VoteSelection

User = get_user_model()


class FinalVotingTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='voter', email='voter@example.com', password='pass123456')
        self.staff = User.objects.create_user(username='staff', email='staff@example.com', password='pass123456', is_staff=True)
        self.election = Election.current()
        self.election.status = 'open'
        self.election.save()
        self.category = BallotCategory.objects.create(name='Approved Category', display_order=100, approved=True)
        self.division = BallotDivision.objects.create(category=self.category, label='Male', required_candidates=2)
        self.one = Candidate.objects.create(division=self.division, name='Candidate One', position=1)
        self.two = Candidate.objects.create(division=self.division, name='Candidate Two', position=2)

    def submit(self, candidate=None):
        self.client.force_login(self.student)
        return self.client.post(reverse('final_voting:submit'), {f'division_{self.division.pk}': candidate or self.one.pk})

    def test_student_only_sees_open_ballot_and_no_live_totals(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('final_voting:ballot'))
        self.assertContains(response, 'Candidate One')
        self.assertContains(response, 'vote-option')
        self.assertContains(response, 'candidate-avatar')
        self.assertNotContains(response, 'votes')
        self.election.status = 'closed'
        self.election.save()
        self.assertContains(self.client.get(reverse('final_voting:ballot')), 'Voting is Closed')

    def test_ballot_stored_and_one_per_student(self):
        response = self.submit()
        self.assertContains(response, 'Congratulations!')
        self.assertEqual(Ballot.objects.count(), 1)
        self.assertEqual(VoteSelection.objects.get().candidate, self.one)
        self.submit(self.two.pk)
        self.assertEqual(Ballot.objects.count(), 1)
        self.assertEqual(VoteSelection.objects.get().candidate, self.one)

    def test_invalid_division_candidate_rejected(self):
        other = BallotDivision.objects.create(category=self.category, label='Female', required_candidates=1)
        outsider = Candidate.objects.create(division=other, name='Outsider', position=1)
        response = self.submit(outsider.pk)
        self.assertEqual(Ballot.objects.count(), 0)
        self.assertEqual(response.status_code, 302)

    def test_incomplete_category_is_not_published(self):
        self.division.candidates.all().delete()
        self.client.force_login(self.student)
        self.assertNotContains(self.client.get(reverse('final_voting:ballot')), 'Approved Category')

    def test_closed_election_rejects_new_ballots(self):
        self.election.status = 'closed'
        self.election.save()
        self.submit()
        self.assertEqual(Ballot.objects.count(), 0)

    def test_tied_results_share_the_same_rank(self):
        second_voter = User.objects.create_user(username='voter2', email='voter2@example.com', password='pass123456')
        ballot_one = Ballot.objects.create(voter=self.student)
        ballot_two = Ballot.objects.create(voter=second_voter)
        VoteSelection.objects.create(ballot=ballot_one, division=self.division, candidate=self.one)
        VoteSelection.objects.create(ballot=ballot_two, division=self.division, candidate=self.two)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('final_voting:results'))
        self.assertContains(response, '#1 Candidate One')
        self.assertContains(response, '#1 Candidate Two')

    def test_nomination_records_remain_separate(self):
        nomination_category = AwardCategory.objects.create(name='Historical nomination')
        draft = NominationDraft.objects.create(user=self.staff, status='submitted')
        nomination = Nomination.objects.create(draft=draft, category=nomination_category, nominator=self.staff, nom_a_first='Old', nom_a_last='Record')
        self.submit()
        self.assertTrue(Nomination.objects.filter(pk=nomination.pk).exists())
        self.assertEqual(VoteSelection.objects.count(), 1)

    def test_regular_user_cannot_access_management_or_results(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('final_voting:manage')).status_code, 302)
        self.assertEqual(self.client.get(reverse('final_voting:results')).status_code, 302)

    def test_staff_can_view_management_and_results(self):
        self.client.force_login(self.staff)
        management = self.client.get(reverse('final_voting:manage'))
        self.assertEqual(management.status_code, 200)
        self.assertContains(management, 'Approve category')
        self.assertEqual(self.client.get(reverse('final_voting:preview')).status_code, 200)
        self.assertEqual(self.client.get(reverse('final_voting:results')).status_code, 200)

    def test_staff_can_approve_all_complete_online_categories_at_once(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('final_voting:manage_action'), {'action': 'approve_all'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BallotCategory.objects.get(name='GIST OF THE BATCH').approved)
        self.assertFalse(BallotCategory.objects.get(name='YAZA OF THE BATCH').approved)
        self.assertFalse(BallotCategory.objects.get(name='BEST DRESSED').approved)

    def test_admin_can_add_candidates_to_new_unpublished_categories_while_open(self):
        Ballot.objects.create(voter=self.student)
        category = BallotCategory.objects.create(name='New Test Category', display_order=102)
        division = BallotDivision.objects.create(category=category, required_candidates=4)
        self.client.force_login(self.staff)
        response = self.client.post(reverse('final_voting:manage_action'), {
            'action': 'candidate_save',
            'division_id': division.pk,
            'name': 'New Candidate',
            'confirmed': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Candidate.objects.filter(division=division, name='New Candidate', confirmed=True).exists())

    def test_shortlist_has_21_categories_and_reseeding_is_idempotent(self):
        before = BallotCategory.objects.count()
        candidate_count = Candidate.objects.count()
        call_command('seed_final_ballot', verbosity=0)
        self.assertEqual(BallotCategory.objects.count(), before)
        self.assertEqual(Candidate.objects.count(), candidate_count)
        self.assertEqual(BallotCategory.objects.count(), 22)  # 21 shortlist entries plus the test category.

    def test_complete_pair_is_one_candidate_selection(self):
        pair_category = BallotCategory.objects.create(name='Best Duo', display_order=101, approved=True)
        pair_division = BallotDivision.objects.create(category=pair_category, required_candidates=1)
        pair = Candidate.objects.create(division=pair_division, position=1, name='First Person and Second Person')
        self.client.force_login(self.student)
        self.client.post(reverse('final_voting:submit'), {
            f'division_{self.division.pk}': self.one.pk,
            f'division_{pair_division.pk}': pair.pk,
        })
        self.assertEqual(VoteSelection.objects.count(), 2)
        self.assertEqual(VoteSelection.objects.get(candidate=pair).candidate.name, 'First Person and Second Person')
