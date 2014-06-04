import os
import json
import logging
import logging.config
import importlib.machinery
from urllib.parse import urlparse
from collections import ChainMap, defaultdict
from os.path import dirname, abspath, join

import requests

import legistar
from legistar.client import Client
from legistar.base import Base, CachedAttr
from legistar.jurisdictions.utils import Tabs, Mimetypes, Views
from legistar.utils.itemgenerator import make_item

JXN_CONFIGS = {}


class ConfigMeta(type):
    '''Metaclass that aggregates jurisdiction config types by root_url
    and division_id.
    '''
    def __new__(meta, name, bases, attrs):
        cls = type.__new__(meta, name, bases, attrs)

        # Track by domain.
        root_url = attrs.get('root_url')
        if root_url is not None:
            JXN_CONFIGS[cls.get_host()] = cls

        # Also OCD id.
        division_id = attrs.get('division_id')
        if division_id is not None:
            JXN_CONFIGS[division_id] = cls

        # Also nicknames.
        for name in attrs.get('nicknames', []):
            JXN_CONFIGS[name] = cls

        meta.collect_itemfuncs(attrs, cls)

        return cls

    @classmethod
    def collect_itemfuncs(meta, attrs, cls):
        '''Aggregates special item functions marked on each
        config subtype.
        '''
        registry = defaultdict(list)
        for name, member in attrs.items():
            if getattr(member, '_is_aggregator_func', False):
                registry[member._pupatype].append(member)
        cls.aggregator_funcs = registry


class Config(Base, metaclass=ConfigMeta):
    '''The base configuration for a Legistar instance. Various parts can be
    overridden.
    '''
    def __init__(self, **kwargs):
        '''Thinking it'd be helpful to store get_scraper kwargs here,
        in case the Config subtype is the most convenient place to put
        a helper function.
        '''
        self.kwargs = kwargs

    SESSION_CLASS = requests.Session

    mimetypes = Mimetypes()
    MIMETYPE_GIF_PDF = ('/images/pdf.gif', 'application/pdf')
    MIMETYPE_EXT_PDF = ('pdf', 'application/pdf')
    MIMETYPE_GIF_VIDEO = ('/images/video.gif', 'application/x-shockwave-flash')
    MIMETYPE_EXT_DOC = ('doc', 'application/vnd.msword')
    MIMETYPE_EXT_DOCX = ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    TAB_TEXT_ID = 'ctl00_tabTop'
    TAB_TEXT_XPATH_TMPL = 'string(//div[@id="%s"]//a[contains(@class, "rtsSelected")])'
    TAB_TEXT_XPATH = TAB_TEXT_XPATH_TMPL % TAB_TEXT_ID

    # These are config options that can be overridden.
    tabs = Tabs()
    EVT_TAB_META = ('Calendar.aspx', 'events')
    ORG_TAB_META = ('Departments.aspx', 'orgs')
    BILL_TAB_META = ('Legislation.aspx', 'bills')
    PPL_TAB_META = ('People.aspx', 'people')

    # Pagination xpaths.
    PGN_CURRENT_PAGE_TMPL = '//*[contains(@class, "%s")]'
    PGN_CURRENT_PAGE_CLASS = 'rgCurrentPage'
    PGN_CURRENT_PAGE_XPATH = PGN_CURRENT_PAGE_TMPL % PGN_CURRENT_PAGE_CLASS
    PGN_NEXT_PAGE_TMPL = '%s/following-sibling::a[1]'
    PGN_NEXT_PAGE_XPATH = 'string(%s/following-sibling::a[1]/@href)' % PGN_CURRENT_PAGE_XPATH

    views = Views()
    PPL_SEARCH_VIEW_CLASS = 'legistar.people.PeopleSearchView'
    PPL_DETAIL_VIEW_CLASS = 'legistar.people.PeopleDetailView'
    PPL_SEARCH_TABLE_CLASS = 'legistar.people.PeopleSearchTable'
    PPL_SEARCH_TABLEROW_CLASS = 'legistar.people.PeopleSearchTableRow'
    PPL_SEARCH_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    PPL_SEARCH_FORM_CLASS = 'legistar.people.PeopleSearchForm'
    PPL_DETAIL_TABLE_CLASS = 'legistar.people.PeopleDetailTable'
    PPL_DETAIL_TABLEROW_CLASS = 'legistar.people.PeopleDetailTableRow'
    PPL_DETAIL_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    PPL_DETAIL_FORM_CLASS = 'legistar.people.PeopleDetailForm'

    BILL_SEARCH_VIEW_CLASS = 'legistar.bills.SearchView'
    BILL_DETAIL_VIEW_CLASS = 'legistar.bills.DetailView'
    BILL_SEARCH_TABLE_CLASS = 'legistar.bills.SearchTable'
    BILL_SEARCH_TABLEROW_CLASS = 'legistar.bills.SearchTableRow'
    BILL_SEARCH_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    BILL_SEARCH_FORM_CLASS = 'legistar.bills.SearchForm'
    BILL_DETAIL_TABLE_CLASS = 'legistar.bills.DetailTable'
    BILL_DETAIL_TABLEROW_CLASS = 'legistar.bills.DetailTableRow'
    BILL_DETAIL_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    BILL_DETAIL_FORM_CLASS = 'legistar.bills.DetailForm'

    NO_RECORDS_FOUND_TEXT = ['No records were found', 'No records to display.']
    RESULTS_TABLE_XPATH = '//table[contains(@class, "rgMaster")]'

    # ------------------------------------------------------------------------
    # Orgs general config.
    # ------------------------------------------------------------------------
    ORG_SEARCH_VIEW_CLASS = 'legistar.orgs.OrgsSearchView'
    ORG_DETAIL_VIEW_CLASS = 'legistar.orgs.OrgsDetailView'
    ORG_SEARCH_TABLE_CLASS = 'legistar.orgs.OrgsSearchTable'
    ORG_SEARCH_TABLEROW_CLASS = 'legistar.orgs.OrgsSearchTableRow'
    ORG_SEARCH_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    ORG_SEARCH_FORM_CLASS = 'legistar.orgs.OrgsSearchForm'
    ORG_DETAIL_TABLE_CLASS = 'legistar.orgs.OrgsDetailTable'
    ORG_DETAIL_TABLEROW_CLASS = 'legistar.orgs.OrgsDetailTableRow'
    ORG_DETAIL_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    ORG_DETAIL_FORM_CLASS = 'legistar.orgs.OrgsDetailForm'

    # Scrapers will be getting this from people pages.
    ORG_SEARCH_TABLE_DETAIL_AVAILABLE = False
    ORG_DETAIL_TABLE_DETAIL_AVAILABLE = False

    ORG_SEARCH_TABLE_TEXT_NAME = 'Department Name'
    ORG_SEARCH_TABLE_TEXT_TYPE = 'Type'
    ORG_SEARCH_TABLE_TEXT_MEETING_LOCATION = 'Meeting Location'
    ORG_SEARCH_TABLE_TEXT_NUM_VACANCIES = 'Vacancies'
    ORG_SEARCH_TABLE_TEXT_NUM_MEMBERS = 'Members'

    ORG_DEFAULT_CLASSIFICATIONS = ChainMap({
        'Department': 'commission',
        'Clerk': 'commission',
        'Executive Office': 'commission',
        'Primary Legislative Body': 'legislature',
        'Secondary Legislative Body': 'legislature',
        'City Council': 'legislature',
        'Board of Supervisors': 'legislature',
        'Agency': 'commission',
        })

    @property
    def _ORG_CLASSIFICATIONS(self):
        '''Make the Config's clasifications inherit from this default set.
        '''
        classn = getattr(self, 'ORG_CLASSIFICATIONS', {})
        return self.ORG_DEFAULT_CLASSIFICATIONS.new_child(classn)

    def get_org_classification(self, orgtype):
        '''Convert the legistar org table `type` column into
        a pupa classification.
        '''
        # Try to get the classn from the subtype.
        classn = self._ORG_CLASSIFICATIONS.get(orgtype)
        if classn is not None:
            return classn

        # Bah, no matches--try to guess it.
        type_lower = orgtype.lower()
        for classn in ('legislature', 'party', 'committee', 'commission'):
            if classn in type_lower:
                return classn

        other = [('board', 'commission')]
        for word, classn in other:
            if work in type_lower:
                return classn

        # Not found--complain.
        msg = '''
            Couldn't convert organization `type` value %r to a pupa
            organization classification (see http://opencivicdata.readthedocs.org/en/latest/data/organization.html#basics).
            Please edit %r by adding a top-level ORG_CLASSIFICATIONS
            dictionary that maps %r value to a pupa classification.'''
        raise ValueError(msg % (orgtype, self.config, orgtype))

    # ------------------------------------------------------------------------
    # Events general config.
    # ------------------------------------------------------------------------
    EVT_SEARCH_VIEW_CLASS = 'legistar.events.EventsSearchView'
    EVT_DETAIL_VIEW_CLASS = 'legistar.events.EventsDetailView'
    EVT_SEARCH_TABLE_CLASS = 'legistar.events.EventsSearchTable'
    EVT_SEARCH_TABLEROW_CLASS = 'legistar.events.EventsSearchTableRow'
    EVT_SEARCH_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    EVT_SEARCH_FORM_CLASS = 'legistar.events.EventsSearchForm'
    EVT_DETAIL_TABLE_CLASS = 'legistar.events.EventsDetailTable'
    EVT_DETAIL_TABLEROW_CLASS = 'legistar.events.EventsDetailTableRow'
    EVT_DETAIL_TABLECELL_CLASS = 'legistar.fields.ElementAccessor'
    EVT_DETAIL_FORM_CLASS = 'legistar.events.EventsDetailForm'

    # ------------------------------------------------------------------------
    # Events search table config.

    # Search params.
    EVT_SEARCH_TIME_PERIOD = 'This Year'
    EVT_SEARCH_BODIES = 'All Committees'
    EVT_SEARCH_BODIES_EL_NAME = 'ctl00$ContentPlaceHolder1$lstBodies'
    EVT_SEARCH_TIME_PERIOD_EL_NAME = 'ctl00$ContentPlaceHolder1$lstYears'
    EVT_SEARCH_CLIENTSTATE_EL_NAME = 'ctl00_ContentPlaceHolder1_lstYears_ClientState'

    # Table
    EVT_SEARCH_TABLE_TEXT_NAME = 'Name'
    EVT_SEARCH_TABLE_TEXT_DATE =  'Meeting Date'
    EVT_SEARCH_TABLE_TEXT_ICAL =  ''
    EVT_SEARCH_TABLE_TEXT_TIME = 'Meeting Time'
    EVT_SEARCH_TABLE_TEXT_LOCATION = 'Meeting Location'
    EVT_SEARCH_TABLE_TEXT_TOPIC = 'Meeting Topic'
    EVT_SEARCH_TABLE_TEXT_DETAILS = 'Meeting Details'
    EVT_SEARCH_TABLE_TEXT_AGENDA = 'Agenda'
    EVT_SEARCH_TABLE_TEXT_MINUTES = 'Minutes'
    EVT_SEARCH_TABLE_TEXT_MEDIA = 'Multimedia'
    EVT_SEARCH_TABLE_TEXT_NOTICE = 'Notice'

    EVT_SEARCH_TABLE_DATETIME_FORMAT = '%m/%d/%Y %I:%M %p'

    EVT_SEARCH_TABLE_PUPA_KEY_NAME = EVT_SEARCH_TABLE_TEXT_TOPIC
    EVT_SEARCH_TABLE_PUPA_KEY_LOCATION = EVT_SEARCH_TABLE_TEXT_LOCATION

    EVT_SEARCH_TABLE_PUPA_PARTICIPANTS = {
        'organization': [EVT_SEARCH_TABLE_TEXT_NAME]
        }

    EVT_SEARCH_TABLE_PUPA_DOCUMENTS = [
        EVT_SEARCH_TABLE_TEXT_AGENDA,
        EVT_SEARCH_TABLE_TEXT_MINUTES,
        EVT_SEARCH_TABLE_TEXT_NOTICE,
        ]

    # ------------------------------------------------------------------------
    # Events detail config.
    EVT_SEARCH_TABLE_DETAIL_AVAILABLE = True

    EVT_DETAIL_TEXT_NAME = EVT_SEARCH_TABLE_TEXT_NAME
    EVT_DETAIL_TEXT_TOPIC = EVT_SEARCH_TABLE_TEXT_TOPIC
    EVT_DETAIL_TEXT_DETAILS = EVT_SEARCH_TABLE_TEXT_DETAILS
    EVT_DETAIL_TEXT_MEDIA = EVT_SEARCH_TABLE_TEXT_MEDIA
    EVT_DETAIL_TEXT_NOTICE = EVT_SEARCH_TABLE_TEXT_NOTICE
    EVT_DETAIL_TEXT_LOCATION = 'Meeting location'
    EVT_DETAIL_TEXT_DATE = 'Date'
    EVT_DETAIL_TEXT_TIME = 'Time'
    EVT_DETAIL_TEXT_VIDEO = 'Meeting video'
    EVT_DETAIL_TEXT_AGENDA = 'Published agenda'
    EVT_DETAIL_TEXT_AGENDA_STATUS = 'Agenda status'
    EVT_DETAIL_TEXT_MINUTES = 'Published minutes'
    EVT_DETAIL_TEXT_MINUTES_STATUS = 'Minutes status'
    EVT_DETAIL_TEXT_SUMMARY = 'Published summary'

    EVT_DETAIL_DATETIME_FORMAT = EVT_SEARCH_TABLE_DATETIME_FORMAT
    EVT_DETAIL_PUPA_KEY_NAME = EVT_DETAIL_TEXT_TOPIC
    EVT_DETAIL_PUPA_KEY_LOCATION = EVT_DETAIL_TEXT_LOCATION

    EVT_DETAIL_PUPA_PARTICIPANTS = {
        'organization': [EVT_DETAIL_TEXT_NAME]
        }

    EVT_DETAIL_PUPA_DOCUMENTS = [
        EVT_DETAIL_TEXT_AGENDA,
        EVT_DETAIL_TEXT_MINUTES,
        EVT_DETAIL_TEXT_NOTICE,
        EVT_DETAIL_TEXT_VIDEO,
        ]

    # Readable text for the agenda table of related bills.
    EVT_DETAIL_TABLE_TEXT_FILE_NUMBER = 'File #'
    EVT_DETAIL_TABLE_TEXT_VERSION = 'Ver.'
    EVT_DETAIL_TABLE_TEXT_NAME = 'Name'
    EVT_DETAIL_TABLE_TEXT_AGENDA_NOTE = 'Agenda Note'
    EVT_DETAIL_TABLE_TEXT_AGENDA_NUMBER = 'Agenda #'
    EVT_DETAIL_TABLE_TEXT_TYPE = 'Type'
    EVT_DETAIL_TABLE_TEXT_TITLE = 'Title'
    EVT_DETAIL_TABLE_TEXT_ACTION = 'Action'
    EVT_DETAIL_TABLE_TEXT_RESULT = 'Result'
    EVT_DETAIL_TABLE_TEXT_ACTION_DETAILS = 'Action Details'
    EVT_DETAIL_TABLE_TEXT_VIDEO = 'Video'
    EVT_DETAIL_TABLE_TEXT_AUDIO = 'Audio'
    EVT_DETAIL_TABLE_TEXT_TRANSCRIPT = 'Transcript'

    # ------------------------------------------------------------------------
    # People search config.
    PPL_SEARCH_TABLE_TEXT_FULLNAME = 'Person Name'
    PPL_SEARCH_TABLE_TEXT_WEBSITE =  'Web Site'
    PPL_SEARCH_TABLE_TEXT_EMAIL =  'E-mail'
    PPL_SEARCH_TABLE_TEXT_FAX = 'Fax'
    PPL_SEARCH_TABLE_TEXT_DISTRICT = 'Ward/Office'
    PPL_SEARCH_TABLE_TEXT_DISTRICT_PHONE = 'Ward Office Phone'
    PPL_SEARCH_TABLE_TEXT_DISTRICT_ADDRESS = 'Ward Office Address'
    PPL_SEARCH_TABLE_TEXT_DISTRICT_ADDRESS_STATE = ('State', 0)
    PPL_SEARCH_TABLE_TEXT_DISTRICT_ADDRESS_CITY = ('City', 0)
    PPL_SEARCH_TABLE_TEXT_DISTRICT_ADDRESS_ZIP = ('Zip', 0)
    PPL_SEARCH_TABLE_TEXT_CITYHALL_PHONE = 'City Hall Phone'
    PPL_SEARCH_TABLE_TEXT_CITYHALL_ADDRESS = 'City Hall Address'
    PPL_SEARCH_TABLE_TEXT_CITYHALL_ADDRESS_STATE = ('State', 1)
    PPL_SEARCH_TABLE_TEXT_CITYHALL_ADDRESS_CITY = ('City', 1)
    PPL_SEARCH_TABLE_TEXT_CITYHALL_ADDRESS_ZIP = ('Zip', 1)

    # Whether people detail pages are available.
    PPL_SEARCH_TABLE_DETAIL_AVAILABLE = True
    # Nonsense to prevent detail queries on detail pages.
    PPL_DETAIL_TABLE_DETAIL_AVAILABLE = False

    PPL_DETAIL_TEXT_FIRSTNAME = 'First name'
    PPL_DETAIL_TEXT_LASTNAME = 'Last name'
    PPL_DETAIL_TEXT_WEBSITE =  'Web site'
    PPL_DETAIL_TEXT_EMAIL = 'E-mail'
    PPL_DETAIL_TEXT_NOTES = 'Notes'

    # This field actually has no label, but this pretends it does,
    # so as to support the same interface.
    PPL_DETAIL_TEXT_PHOTO = 'Photo'

    # The string to indicate that person's rep'n is "at-large".
    DEFAULT_AT_LARGE_STRING = 'At-Large'
    # The string indicating person's membership in the council, for example.
    # This is usually the first row in the person detail chamber.
    # It's the string value of the first PPL_MEMB_TABLE_TEXT_ROLE
    TOPLEVEL_ORG_MEMBERSHIP_TITLE_TEXT = 'Council Member'
    TOPLEVEL_ORG_MEMBERSHIP_NAME_TEXT = 'City Council'

    PPL_DETAIL_TABLE_TEXT_ORG = 'Department Name'
    PPL_DETAIL_TABLE_TEXT_ROLE = 'Title'
    PPL_DETAIL_TABLE_TEXT_START_DATE = 'Start Date'
    PPL_DETAIL_TABLE_TEXT_END_DATE = 'End Date'
    PPL_DETAIL_TABLE_TEXT_APPOINTED_BY = 'Appointed By'

    # ------------------------------------------------------------------------
    # Bill search config.
    BILL_SIMPLE_SEARCH_TEXT = '<<< Simple Search'
    BILL_ADVANCED_SEARCH_TEXT = 'Detailed Search >>>'

    # ------------------------------------------------------------------------
    # Settings to prevent web requests during testing.

    # Makes the form use the default table data without posting a query.
    USING_TEST_CONFIG = False

    # Requests args.
    proxies = dict.fromkeys(['http', 'https'], 'http://localhost:8080')
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.1.6) '
            'Gecko/20070725 Firefox/2.0.0.6')
        }
    requests_kwargs = dict(
        proxies=proxies,
        headers=headers)
    requests_kwargs = {}

    @classmethod
    def get_host(cls):
        return urlparse(cls.root_url).netloc

    def get_session(self):
        '''Return a requests.Session subtype, or something that provides
        the same interface.
        '''
        session = self.kwargs.get('session')
        if session is None:
            session = self.SESSION_CLASS()
        return session

    def get_client(self):
        '''The requests.Session-like object used to make web requests;
        usually a scrapelib.Scraper.
        '''
        return Client(self)

    def get_logger(self):
        '''Get a configured logger.
        '''
        logging.config.dictConfig(self.LOGGING_CONFIG)
        logger = logging.getLogger('legistar')
        if 'loglevel' in self.kwargs:
            logger.setLevel(self.kwargs['loglevel'])
        return logger

    @CachedAttr
    def chainmap(self):
        '''An inheritable/overridable dict for this config's helper
        views to access. Make it initially point back to this config object.

        Other objects that inherit this chainmap can access self.info, etc.
        '''
        logger = self.get_logger()
        chainmap = ChainMap()
        chainmap.update(
            config=self,
            url=self.root_url,
            client=self.get_client(),
            info=logger.info,
            error=logger.error,
            debug=logger.debug,
            warning=logger.warning,
            critical=logger.critical)
        return chainmap

    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': "%(asctime)s %(levelname)s %(name)s: %(message)s",
                'datefmt': '%H:%M:%S'
            }
        },
        'handlers': {
            'default': {'level': 'DEBUG',
                        'class': 'legistar.utils.ansistrm.ColorizingStreamHandler',
                        'formatter': 'standard'},
        },
        'loggers': {
            'legistar': {
                'handlers': ['default'], 'level': 'DEBUG', 'propagate': False
            },
            # 'requests': {
            #     'handlers': ['default'], 'level': 'DEBUG', 'propagate': False
            # },
        },
    }

    # -----------------------------------------------------------------------
    # Stuff related to testing.
    # -----------------------------------------------------------------------
    def get_assertions_dir(self, year):
        legistar_root = abspath(join(dirname(legistar.__file__), '..'))
        assertions = join(legistar_root, 'assertions')
        _, relpath = self.division_id.split('/', 1)
        fullpath = join(assertions, relpath, year)
        return fullpath

    def ensure_assertions_dir(self, year):
        assertions_dir = self.get_assertions_dir(year)
        if not os.path.isdir(assertions_dir):
            os.makedirs(assertions_dir)
        return assertions_dir

    def gen_assertions(self, year, pupatype):
        assertions_dir = self.ensure_assertions_dir(year)
        filename = join(assertions_dir, '%s.py' % pupatype)
        loader = importlib.machinery.SourceFileLoader(pupatype, filename)
        mod = loader.load_module()
        if not hasattr(mod, 'assertions'):
            msg = ('The file %r must define a module-level sequence '
                   '`assertions` containing the assertion data.')
            raise Exception(msg % filename)
        yield from iter(mod.assertions)