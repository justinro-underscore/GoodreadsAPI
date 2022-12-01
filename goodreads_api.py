from bs4 import BeautifulSoup
import requests
import json
from os.path import exists
from datetime import datetime

# Deprecated, this is handled even more easily by the /auto_complete endpoint
def get_id_by_search(title, author=None):
    print('Searching for {}{}...'.format(title, ' by ' + author if author is not None else ''))
    search_request = title + (' ' + author if author is not None else '')
    r = requests.get('https://www.goodreads.com/search', params={
        'q': search_request,
        'search_type': 'books',
        'search[field]': 'on'
    });
    if r.status_code != 200:
        print('Search request failed!')
        return -1

    doc = BeautifulSoup(r.text, 'html.parser')
    book_table = doc.table
    if book_table is None:
        if author is None:
            print('No results found...')
            return -1
        else:
            print('No results found, trying just title...')
            return get_id_by_search(title)

    book_entry = book_table.find('tr')
    book_id = book_entry.find(class_='u-anchorTarget')['id']
    title = book_entry.find(class_='bookTitle').get_text().strip()
    author = book_entry.find(class_='authorName').get_text().strip()
    print('ID for {} by {} - {}'.format(title, author, book_id))
    return book_id

def get_book_url(title, author=None, debug=False):
    if debug:
        print('Searching for {}{}...'.format(title, ' by ' + author if author is not None else ''))
    search_request = title + (' ' + author if author is not None else '')
    r = requests.get('https://www.goodreads.com/book/auto_complete', params={
        'q': search_request
    });
    if r.status_code != 200:
        if debug:
            print('Search request failed!')
        return None

    results = r.json()
    if len(results) == 0:
        if author is None:
            if debug:
                print('No results found')
            return None
        else:
            if debug:
                print('No results found, trying just title...')
            return get_book_url(title, None, debug)

    # TODO Allow for selecting the book that's requested
    book_entry = results[0]
    book_url = book_entry['bookUrl']
    book_title = book_entry['title']
    if book_title != title:
        print('Title mismatch - Given: \'{}\' Found: \'{}\''.format(title, book_title))
    book_author = book_entry['author']['name']
    if author is not None and book_author != author:
        print('Author mismatch - Given: \'{}\' Found: \'{}\''.format(author, book_author))
    return book_url

def get_book_info_from_url(title, url, debug=False):
    if debug:
        print('Requesting book at {}...'.format(url))
    r = requests.get('https://www.goodreads.com/' + url, headers={
        'Accept': 'application/json'
    })
    if r.status_code != 200:
        if debug:
            print('Search request failed!')
        return {}
    doc = BeautifulSoup(r.text, 'html.parser')

    goodreads_data_elem = doc.find('script', id='__NEXT_DATA__')
    if goodreads_data_elem is None:
        # TODO Retry automatically
        print('Failed, try again')
        return {}
    goodreads_data_raw = json.loads(goodreads_data_elem.string)

    f = open(_get_cached_book_path(title), 'w')
    f.write(json.dumps(goodreads_data_raw, indent=4))
    f.close()

    return _parse_book_data(goodreads_data_raw)

def save_book_info(book_data):
    filename = _get_saved_book_data(book_data['title'])
    f = open(filename, 'w')
    f.write(json.dumps(book_data, indent=4))
    f.close()
    return filename

def get_book_info(query, author=None):
    # TODO Replace filename with actual title, rather than the query title
    if exists(_get_cached_book_path(query)):
        f = open(_get_cached_book_path(query), 'r')
        goodreads_data_str = f.read()
        f.close()
        return _parse_book_data(json.loads(goodreads_data_str))
    else:
        url = get_book_url(query, author)
        if url is not None:
            return get_book_info_from_url(query, url)
        return {}

### PRIVATE METHODS ###

def _parse_book_data(goodreads_data_raw):
    goodreads_data = goodreads_data_raw['props']['pageProps']['apolloState']

    info_key = None
    work_key = None
    for key in goodreads_data.keys():
        if key.find('Book:') == 0:
            info_key = key
        elif key.find('Work:') == 0:
            work_key = key
    if not info_key:
        print('Info key not found')
        return {}
    if not work_key:
        print('Work key not found')
        return {}
    # Contributor keys will come from the info data

    gr_info_data = goodreads_data[info_key]
    book_data = {
        'title': gr_info_data['title'],
        'titleComplete': gr_info_data['titleComplete'],
        'description': gr_info_data['description({\"stripped\":true})'],
        'goodreadsUrl': gr_info_data['webUrl'],
        'coverImage': gr_info_data['imageUrl']
    }

    genres = []
    for gr_genre_info in gr_info_data['bookGenres']:
        genres.append(gr_genre_info['genre']['name'])
    book_data['genres'] = genres

    series_info = []
    for gr_series_info in gr_info_data['bookSeries']:
        series_info.append({
            'key': gr_series_info['series']['__ref'],
            'number': gr_series_info['userPosition']
        })
    series = []
    for series_data in series_info:
        book_series_data = {
            'name': goodreads_data[series_data['key']]['title']
        }
        if series_data['number'] != '':
            book_series_data['number'] = int(series_data['number'])
        series.append(book_series_data)
    book_data['series'] = series

    gr_book_details = gr_info_data['details']
    book_details = {
        'format': gr_book_details['format'],
        'numPages': gr_book_details['numPages'],
        'publicationTime': gr_book_details['publicationTime'],
        'publisher': gr_book_details['publisher'],
        'isbn': gr_book_details['isbn'],
        'isbn13': gr_book_details['isbn13'],
        'language': gr_book_details['language']['name']
    }
    publication_date = datetime.utcfromtimestamp(gr_book_details['publicationTime'] / 1000)
    book_details['publicationDate'] = publication_date.strftime('%m/%d/%Y')
    book_data['bookDetails'] = book_details

    def parse_book_link(book_link_data):
        book_link = {
            'name': book_link_data['name'],
            'url': book_link_data['url'],
            'linkType': book_link_data['__typename']
        }
        if 'ebookPrice' in book_link_data:
            book_link['ebookPrice'] = book_link_data['ebookPrice']
        return book_link

    gr_book_links = gr_info_data['links({})']
    book_links = [parse_book_link(gr_book_links['primaryAffiliateLink'])]
    for gr_secondary_book_link_data in gr_book_links['secondaryAffiliateLinks']:
        book_links.append(parse_book_link(gr_secondary_book_link_data))
    for gr_library_book_link_data in gr_book_links['libraryLinks']:
        book_links.append(parse_book_link(gr_library_book_link_data))
    book_data['links'] = book_links

    primary_contributor = {
        'primary': True,
        'key': gr_info_data['primaryContributorEdge']['node']['__ref'],
        'role': gr_info_data['primaryContributorEdge']['role']
    }
    contributors = [primary_contributor]
    for gr_secondary_contributor_data in gr_info_data['secondaryContributorEdges']:
        secondary_contributor = {
            'primary': False,
            'key': gr_secondary_contributor_data['node']['__ref'],
            'role': gr_secondary_contributor_data['role']
        }
        contributors.append(secondary_contributor)

    contributors_data = []
    for contributor in contributors:
        gr_contributor_data = goodreads_data[contributor['key']]
        contributor_data = {
            'name': gr_contributor_data['name'],
            'goodreadsUrl': gr_contributor_data['webUrl'],
            'primary': contributor['primary'],
            'role': contributor['role']
        }
        if 'description' in gr_contributor_data:
            contributor_data['description'] = gr_contributor_data['description']
        if 'works' in gr_contributor_data:
            contributor_data['numWorks'] = gr_contributor_data['works']['totalCount']
        if 'profileImageUrl' in gr_contributor_data:
            contributor_data['profileImage'] = gr_contributor_data['profileImageUrl']
        if 'followers' in gr_contributor_data:
            contributor_data['followers'] = gr_contributor_data['followers']['totalCount']
        contributors_data.append(contributor_data)
    book_data['contributors'] = contributors_data

    gr_root_data = goodreads_data['ROOT_QUERY']
    for key in gr_root_data.keys():
        if 'getAdsTargeting' in key:
            book_data['adult'] = gr_root_data[key]['contextual']['adult']
            break

    gr_work_data = goodreads_data[work_key]
    gr_work_details_data = gr_work_data['details']
    book_data['originalTitle'] = gr_work_details_data['originalTitle']

    awards = []
    for gr_award_data in gr_work_details_data['awardsWon']:
        award_data = {
            'name': gr_award_data['name'],
            'goodreadsUrl': gr_award_data['webUrl'],
            'category': gr_award_data['category'],
            'hasWon': gr_award_data['hasWon']
        }
        awarded_at_date = datetime.utcfromtimestamp(gr_award_data['awardedAt'] / 1000)
        award_data['awardDate'] = awarded_at_date.strftime('%m/%d/%Y')
        awards.append(award_data)
    book_data['awards'] = awards

    places = []
    for gr_place_data in gr_work_details_data['places']:
        places.append({
            'name': gr_place_data['name'],
            'country': gr_place_data['countryName'],
            'year': gr_place_data['year'],
            'goodreadsUrl': gr_place_data['webUrl'],
        })
    if len(places) > 0:
        book_data['places'] = places

    characters = []
    for gr_character_data in gr_work_details_data['characters']:
        characters.append({
            'name': gr_character_data['name'],
            'goodreadsUrl': gr_character_data['webUrl'],
        })
    if len(characters) > 0:
        book_data['characters'] = characters

    gr_stats_data = gr_work_data['stats']
    rating_data = {
        'averageRating': gr_stats_data['averageRating'],
        'ratingsCount': gr_stats_data['ratingsCount'],
    }
    ratingsDist = []
    for i, count in enumerate(gr_stats_data['ratingsCountDist']):
        ratingsDist.append({
            'rating': i + 1,
            'count': count
        })
    rating_data['ratingsCountDistribution'] = ratingsDist
    rating_data['textReviewsCount'] = gr_stats_data['textReviewsCount']
    text_review_lang_counts = []
    for gr_text_review_counts in gr_stats_data['textReviewsLanguageCounts']:
        text_review_lang_counts.append({
            'language': gr_text_review_counts['isoLanguageCode'],
            'count': gr_text_review_counts['count']
        })
    rating_data['textReviewsLanguageCounts'] = text_review_lang_counts
    book_data['stats'] = rating_data

    return book_data

def _get_cached_book_path(title):
    return 'books_data_raw/{}.json'.format(title.replace(' ', '_').lower())

def _get_saved_book_data(title):
    return 'books_data/{}.json'.format(title.replace(' ', '_').lower())
