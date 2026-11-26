from django.conf import settings
from django.db import models


class Election(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('ready', 'Ready for approval'), ('open', 'Open'), ('closed', 'Closed')]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='draft')
    allow_ballot_edits = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_elections')
    approved_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Final voting ({self.status})'


class BallotCategory(models.Model):
    METHOD_CHOICES = [('online', 'Online voting'), ('academic', 'Academic selection'), ('dinner', 'Finale dinner')]
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(unique=True)
    method = models.CharField(max_length=12, choices=METHOD_CHOICES, default='online')
    approved = models.BooleanField(default=False)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name


class BallotDivision(models.Model):
    category = models.ForeignKey(BallotCategory, related_name='divisions', on_delete=models.CASCADE)
    label = models.CharField(max_length=80, default='')
    display_order = models.PositiveSmallIntegerField(default=1)
    required_candidates = models.PositiveSmallIntegerField(default=4)
    class Meta:
        ordering = ['display_order', 'id']
        constraints = [models.UniqueConstraint(fields=['category', 'label'], name='unique_ballot_division_label')]
    def __str__(self):
        return f'{self.category}: {self.label}' if self.label else self.category.name


class Candidate(models.Model):
    division = models.ForeignKey(BallotDivision, related_name='candidates', on_delete=models.CASCADE)
    name = models.CharField(max_length=240)
    position = models.PositiveSmallIntegerField(default=1)
    confirmed = models.BooleanField(default=True)
    dinner_result = models.BooleanField(default=False)
    winner_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['position', 'id']
        constraints = [models.UniqueConstraint(fields=['division', 'position'], name='unique_candidate_position')]
    def __str__(self):
        return self.name


class Ballot(models.Model):
    voter = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='final_ballot', on_delete=models.PROTECT)
    submitted_at = models.DateTimeField(auto_now_add=True)


class VoteSelection(models.Model):
    ballot = models.ForeignKey(Ballot, related_name='selections', on_delete=models.PROTECT)
    division = models.ForeignKey(BallotDivision, related_name='selections', on_delete=models.PROTECT)
    candidate = models.ForeignKey(Candidate, related_name='selections', on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['ballot', 'division'], name='unique_ballot_division_vote')]


class VotingAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
