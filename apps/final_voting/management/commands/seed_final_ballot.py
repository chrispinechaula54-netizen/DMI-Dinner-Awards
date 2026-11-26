from django.core.management.base import BaseCommand
from apps.final_voting.models import BallotCategory, BallotDivision, Candidate


# Division labels, ordered candidate names. Explicit pending entries preserve shortlist positions.
SHORTLIST = [
 ('YAZA OF THE BATCH', 'academic', []),
 ('GIST OF THE BATCH', 'online', [('Gist Papi – Male', ['Douglas Nyala','Morgan Mwanza','Kondwani Genesis','Genesis']),('Gist Mami – Female',['Catherine Nyama','Priscilla Mwenela','Esnart','Josephine Matenje'])]),
 ('ENJOYMENT MAMI AND ENJOYMENT PAPI','online',[('Enjoyment Papi – Male',['Eustace Masache','Mphatso','Kondwani Buleya','Moses Lemoe Lungu']),('Enjoyment Mami – Female',['Leticia Moffat','Clara Mataya','Gloria Mwatsika'])]),
 ('MOST SMART','online',[('Male',['Chancy Edward','Jonathan Linguni','Clement Nkhonya','TO BE CONFIRMED']),('Female',['Sarah Damson','Tamandani Banda','Happiness Bizwick','TO BE CONFIRMED'])]),
 ('SWAZI OF THE BATCH','online',[('Male',['Hanleck Chidothi',"Alliah M'Madi",'Future Cherani','Ovilera']),('Female',['Pemphero Wame','Edda','Getrude Yota','TO BE CONFIRMED'])]),
 ('STONER OF THE BATCH','online',[('Male',['Peter Grok 19','Young Lt','Jabulani Kalimbe','Peter']),('Female',['Clara Mataya','Yevettte','Hanna Jane Navaya','Victoria Chakhama'])]),
 ('CHIDAKWA OF THE BATCH','online',[('Male',['Moses Laison Lungu','Precious Kasiyagoli','Ovie Jamali','TO BE CONFIRMED']),('Female',['Molles Phiri','Thoko Phiri','Retticia Mwinibwalo','TO BE CONFIRMED'])]),
 ('PRAYER WARRIOR OF THE BATCH','online',[('Male',['Jonathan Linguni','Chimwemwe','Mbolembole','TO BE CONFIRMED']),('Female',['Tamandani Banda','Edda','TO BE CONFIRMED','TO BE CONFIRMED'])]),
 ('MOST INTERACTIVE','online',[('Male',['Ramsey Scott Mbolembole','Lumbani Moyo','Wongani Moyo','TO BE CONFIRMED']),('Female',['Hanna Jane Navaya','Catherine Nyama','Hannah Navaya','Viana'])]),
 ('CLASS REP OF THE BATCH','online',[('Male',['Benjamin Khoko','Steven Magalasi','Mike Nambazo','Steven Mangalasi']),('Female',['Clara Mataya','Fatima Idana','TO BE CONFIRMED','TO BE CONFIRMED'])]),
 ('MOST BEAUTIFUL FEMALE OF THE BATCH','online',[('', ['Chisomo Chimasula','Tadala Safari','Isha Shaibu','TO BE CONFIRMED'])]),
 ('MOST HANDSOME MALE OF THE BATCH','online',[('', ['Emmanuel Gondwe','Harry Potter Banda','Ramsey Scott Mbolembole','Hope Nandolo'])]),
 ('BEST DRESSED','dinner',[('',[])]),
 ('BEST DUO','online',[('', ['Buccah Namondwe and Francis Casper Ndeule','Eustace Masache and Harry Banda','Niwa Mzaya and Thocco Bondwe','Getrude Yota and Happiness Biziwick'])]),
 ('COUPLE OF THE BATCH','online',[('', ['Felix Phiri and Bridget Chinyanga','Tadala Mabedi and Peter Kandulu','TO BE CONFIRMED','TO BE CONFIRMED'])]),
 ('BEST ENTERTAINER OF THE BATCH','online',[('Male',['Buccah Namondwe','Ramsey Scott Mbolembole','Eustace Masache','TO BE CONFIRMED']),('Female',['Ivy Mwandama','Vianna Mwandanda','Josephine Matenge','Viana'])]),
 ('TECH GENIUS OF THE BATCH','online',[('', ['Joel Ndege','Benja','TO BE CONFIRMED','TO BE CONFIRMED'])]),
 ('INNOVATOR OF THE BATCH','online',[('', ['Jabulan Mayenda','Felix Oscar Phiri','Kondwani Paul Buleya','Desire'])]),
 ('PRODUCER OF THE BATCH','online',[('', ['Vincent Kondowe','Jonathan Phalula','TO BE CONFIRMED','TO BE CONFIRMED'])]),
 ('RESILIENT OF THE BATCH','online',[('Male',['Gomez Chavula','Uchizi Mlowoka','Ozil','TO BE CONFIRMED']),('Female',['Amina Maulana','Emily Matapila','Thoko','TO BE CONFIRMED'])]),
 ('HUSTLER OF THE BATCH','online',[('Male',['Douglas Nyala','Khenzo Nambazo','Dagalus Nyala','Hastings Tamaona']),('Female',['Happiness Biziwick','Nancy Mwanza','Vanessa','Faith Chiwaula'])]),
 ('PLAYER OF THE BATCH','online',[('Football Players',['Weston Chinoko','Zonke','Buccah','Lumbani (Ongani)']),('Netball Players',['Alisha','Constance','Esnart','Faith'])]),
 ('ARTIST OF THE BATCH','online',[('Male',['Shegu','Uchiz']),('Female',['Laura'])]),
 ('BAYALA OF THE BATCH','online',[('', ['Gomez Chavula','Cruger'])]),
]

class Command(BaseCommand):
    help = 'Idempotently initialize the official final voting shortlist.'
    def handle(self, *args, **options):
        for order, (name, method, divisions) in enumerate(SHORTLIST, 1):
            category, _ = BallotCategory.objects.get_or_create(display_order=order, defaults={'name':name,'method':method})
            if method == 'academic':
                continue
            for div_order, (label, names) in enumerate(divisions, 1):
                division, _ = BallotDivision.objects.get_or_create(category=category, label=label, defaults={'display_order':div_order,'required_candidates':4})
                for position, candidate_name in enumerate(names, 1):
                    pending = candidate_name == 'TO BE CONFIRMED'
                    Candidate.objects.get_or_create(division=division, position=position, defaults={'name':candidate_name,'confirmed':not pending})
        self.stdout.write(self.style.SUCCESS('Final voting shortlist initialized.'))
