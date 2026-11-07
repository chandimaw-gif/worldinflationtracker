"""
Management command: seed_article_drafts

Creates the eight proposed Insights articles as unpublished drafts. Existing
articles are never changed. Drafts are outlines for the owner to write up; they
cannot be published while they contain TODO-OWNER or have no author name.
"""

from django.core.management.base import BaseCommand

from core.models import Article

CCPI_RELEASE = 'https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/press/pr/press_20261030_inflation_in_october_2026_ccpi_e.pdf'
RELEASES_PAGE = 'https://www.cbsl.gov.lk/en/measures-of-consumer-price-inflation'

DRAFTS = [
    ('sri-lanka-inflation-october-2026', 'Sri Lanka inflation, October 2026: what changed and why',
     'What the October 2026 CCPI release shows, and which price groups moved most.', f"""
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## The headline number
Figures from the [CBSL release of 30 October 2026]({CCPI_RELEASE}):

- CCPI (2021=100): 209.9 in October, 209.1 in September
- Headline inflation (year on year): 8.3%, up from 8.0%
- Core inflation (year on year): 5.6%, up from 5.4%
- Food inflation: 8.8%, up from 8.7%. Non-food inflation: 8.0%, up from 7.7%
- Monthly change in the index: 0.35%

## What drove the month
CBSL attributes most of the monthly rise to non-food prices, mainly Restaurants and Hotels.
TODO-OWNER: add your explanation of what this means for households.

## How this compares with the target
CBSL's target is 5%. TODO-OWNER: explain the gap using the release's wording, and link to the 5% target article.

## What to watch next
TODO-OWNER: summarise CBSL's stated outlook from the release, clearly attributed to CBSL.
"""),
    ('rupee-2026-usd-lkr', 'The rupee in 2026: how USD/LKR has moved and what drives it',
     'How the rupee has moved against the US dollar during 2026, using the rates on this site.', """
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## The year so far
[DATA: chart and start, high, low and latest USD/LKR from /exchange-rates/]

Explain that the series changes source: monthly mid-market rates to May 2026, CBSL TT selling rates from June 2026. Do not compare across the two as if they were the same measure.

## What moves the rupee
TODO-OWNER: verify each driver you mention against a CBSL publication and cite it.

## What it means for prices at home
TODO-OWNER: explain the link to imported goods and fuel, with a cited source.
"""),
    ('ccpi-vs-ncpi', 'CCPI vs NCPI: which inflation number should you follow?',
     'The difference between Sri Lanka\'s two main consumer price indices, and when each is useful.', f"""
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## Two indices
CCPI is compiled by the Department of Census and Statistics and covers urban households in the Colombo district ([CBSL CCPI releases]({RELEASES_PAGE})).

TODO-OWNER: verify and describe NCPI's coverage, publication timing and latest value from the DCS or CBSL. NCPI is not in this site's database.

## Why they can differ
TODO-OWNER: verify. Explain coverage and weights.

## Which should you use?
Give practical guidance for readers, in your own words.
"""),
    ('how-to-read-the-ccpi', 'How to read the Colombo Consumer Price Index, with a worked example',
     'What an index number means, and how to turn it into an inflation rate yourself.', f"""
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## What the index number means
The CCPI uses 2021 as its base, so 2021 = 100 ([CBSL release]({CCPI_RELEASE})).

## Worked example
Year-on-year inflation for October 2026, from CBSL's published index numbers:

- October 2026: 209.9
- October 2025: 193.8
- (209.9 - 193.8) / 193.8 x 100 = 8.3%

This matches CBSL's published 8.3%.

## Monthly and annual-average measures
Explain the difference, using the release's table.

## Common mistakes
TODO-OWNER: for example, confusing the index level with the inflation rate.
"""),
    ('opr-loans-and-savings', "What the Central Bank's policy rate (OPR) means for loans and savings",
     'What the Overnight Policy Rate is, and how a change can reach borrowers and savers.', """
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## What the OPR is
TODO-OWNER: verify the definition against CBSL's monetary policy pages and cite them.

[DATA: latest OPR and its date, from /exchange-rates/]

## How a change reaches you
Loans, then savings. TODO-OWNER: verify any example rates against bank or CBSL sources.

## Why the Central Bank changes it
Link to the 5% target article.
"""),
    ('how-we-calculate-our-price-index', 'How we calculate our own price index, in plain English',
     'How World Inflation Tracker collects prices and why its own index has not launched yet.', """
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## Why build an independent index?
TODO-OWNER: your own reasons.

## What we collect
[DATA: number of tracked items and sources, from /methodology/ and /price-log/]

## How the calculation works
Plain-English version of the fixed-basket method on /methodology/.

## Why it is not published yet
Be open about this: not enough consistent price history yet. See the note on /methodology/.
"""),
    ('fuel-prices-and-household-costs', 'Fuel price changes and household costs in Sri Lanka',
     'How fuel price revisions show up in the wider cost of living, using logged fuel prices.', f"""
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## What has happened to fuel prices
[DATA: diesel and petrol price changes from /price-log/, default "changes only" view]

## From the pump to the household budget
The [October 2026 CBSL release]({CCPI_RELEASE}) shows Transport as the highest year-on-year subcategory.
TODO-OWNER: verify the figure against the release's chart before quoting it.

## What households can watch
Original, practical guidance. No invented figures.
"""),
    ('sri-lanka-5-percent-inflation-target', "Sri Lanka's 5% inflation target, explained",
     'What the 5% target means, who set it, and how current inflation compares.', f"""
> TODO-OWNER: outline only. Write 600 to 1,000 words in your own words, then delete these notes.

## The target
Per the [CBSL release of 30 October 2026]({CCPI_RELEASE}), the 5% target was first agreed under the Monetary Policy Framework Agreement of October 2023 and retained under the new agreement signed in October 2026.

## Why 5%?
TODO-OWNER: verify and cite CBSL's reasoning.

## Where inflation is now
Headline inflation was 8.3% in October 2026, per the same release. [DATA: chart from the Dashboard]

## What happens when inflation misses
TODO-OWNER: verify against the agreement's terms.
"""),
]


class Command(BaseCommand):
    help = 'Create the proposed Insights articles as unpublished drafts'

    def handle(self, *args, **options):
        created = 0
        for slug, title, summary, body in DRAFTS:
            _, was_created = Article.objects.get_or_create(
                slug=slug,
                defaults={'title': title, 'summary': summary, 'body': body.strip(), 'status': Article.DRAFT},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'{created} drafts created; {len(DRAFTS) - created} already existed.'))
