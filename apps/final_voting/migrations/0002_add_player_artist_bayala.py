from django.db import migrations


NEW_CATEGORIES = [
    (22, 'PLAYER OF THE BATCH', 'online', [
        ('Football Players', ['Weston Chinoko', 'Zonke', 'Buccah', 'Lumbani (Ongani)']),
        ('Netball Players', ['Alisha', 'Constance', 'Esnart', 'Faith']),
    ]),
    (23, 'ARTIST OF THE BATCH', 'online', [
        ('Male', ['Shegu', 'Uchiz']),
        ('Female', ['Laura']),
    ]),
    (24, 'BAYALA OF THE BATCH', 'online', [
        ('', ['Gomez Chavula', 'Cruger']),
    ]),
]


def add_categories(apps, schema_editor):
    Category = apps.get_model('final_voting', 'BallotCategory')
    Division = apps.get_model('final_voting', 'BallotDivision')
    Candidate = apps.get_model('final_voting', 'Candidate')
    database = schema_editor.connection.alias

    for order, name, method, divisions in NEW_CATEGORIES:
        category, _ = Category.objects.using(database).get_or_create(
            display_order=order,
            defaults={'name': name, 'method': method},
        )
        for div_order, (label, names) in enumerate(divisions, 1):
            division, _ = Division.objects.using(database).get_or_create(
                category_id=category.pk,
                label=label,
                defaults={'display_order': div_order, 'required_candidates': 4},
            )
            for position, candidate_name in enumerate(names, 1):
                Candidate.objects.using(database).get_or_create(
                    division_id=division.pk,
                    position=position,
                    defaults={'name': candidate_name, 'confirmed': True},
                )


class Migration(migrations.Migration):
    dependencies = [('final_voting', '0001_initial')]

    operations = [migrations.RunPython(add_categories, migrations.RunPython.noop)]
