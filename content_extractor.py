import re
from html import unescape
import requests
from bs4 import BeautifulSoup


DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ZENODO_PATTERN = re.compile(r"zenodo\.org/(?:record|records)/(\d+)",re.IGNORECASE)
DEFAULT_TIMEOUT = 15


class ContentExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EthicalFAIRIPAnalyzer/2.0"
        })

    def extract(self, user_input):
        value = str(user_input or "").strip()

        if not value:
            return self._empty_record("No input provided.")

        zenodo_id = self._find_zenodo_id(value)

        if zenodo_id:
            return self._fetch_zenodo(zenodo_id)

        doi = self._find_doi(value)

        if doi:
            return self._fetch_doi(doi)

        if value.startswith(("http://", "https://")):
            return self._fetch_webpage(value)

        return self._parse_free_text(value)

    def _fetch_doi(self, doi):
        datacite_result = self._fetch_datacite(doi)

        if datacite_result:
            return datacite_result

        crossref_result = self._fetch_crossref(doi)

        if crossref_result:
            return crossref_result

        return self._empty_record(
            f"Could not resolve DOI: {doi}",
            doi=doi,
            url=f"https://doi.org/{doi}"
        )

    def _fetch_zenodo(self, record_id):
        api_url = (
            f"https://zenodo.org/api/records/"
            f"{record_id}"
        )

        try:
            response = self.session.get(
                api_url,
                timeout=DEFAULT_TIMEOUT
            )

        except requests.RequestException as error:
            return self._empty_record(
                f"Zenodo request failed: {error}",
                url=(
                    f"https://zenodo.org/records/"
                    f"{record_id}"
                )
            )

        if not response.ok:
            return self._empty_record(
                (
                    f"Zenodo record {record_id} "
                    f"could not be retrieved."
                ),
                url=(
                    f"https://zenodo.org/records/"
                    f"{record_id}"
                )
            )

        try:
            data = response.json()

        except ValueError:
            return self._empty_record(
                "Zenodo returned invalid JSON.",
                url=(
                    f"https://zenodo.org/records/"
                    f"{record_id}"
                )
            )

        metadata = data.get(
            "metadata",
            {}
        )

        links = data.get(
            "links",
            {}
        )

        description = self._clean_html(
            metadata.get("description")
        )

        return {
            "kind": self._resource_type(
                metadata.get("resource_type")
            ),
            "title": metadata.get("title"),
            "authors": self._creator_names(
                metadata.get("creators", [])
            ),
            "author_details": metadata.get(
                "creators",
                []
            ),
            "publication_date": metadata.get(
                "publication_date"
            ),
            "publisher": (
                metadata.get("publisher")
                or "Zenodo"
            ),
            "licence_string": self._licence_value(
                metadata.get("license")
                or metadata.get("licence")
            ),
            "doi": (
                data.get("doi")
                or metadata.get("doi")
            ),
            "url": (
                links.get("self_html")
                or links.get("html")
                or (
                    f"https://zenodo.org/records/"
                    f"{record_id}"
                )
            ),
            "description": description,
            "keywords": metadata.get(
                "keywords",
                []
            ),
            "version": metadata.get("version"),
            "files": self._normalise_zenodo_files(
                data.get("files", [])
            ),
            "related_identifiers": metadata.get(
                "related_identifiers",
                []
            ),
            "access_right": (
                metadata.get("access_right")
                or "open"
            ),
            "embargo_date": metadata.get(
                "embargo_date"
            ),
            "funding": metadata.get(
                "grants",
                []
            ),
            "source": "zenodo",
            "fetch_status": "success",
            "metadata_machine_readable": True,
            "repository_api_available": True,
            "raw_text": description
        }

    def _fetch_datacite(self, doi):
        api_url = (
            f"https://api.datacite.org/dois/"
            f"{doi}"
        )

        try:
            response = self.session.get(
                api_url,
                timeout=DEFAULT_TIMEOUT
            )

        except requests.RequestException:
            return None

        if not response.ok:
            return None

        try:
            attributes = response.json().get(
                "data",
                {}
            ).get(
                "attributes",
                {}
            )

        except ValueError:
            return None

        if not attributes:
            return None

        types = attributes.get(
            "types",
            {}
        )

        rights = attributes.get(
            "rightsList",
            []
        )

        description = self._first_description(
            attributes.get(
                "descriptions",
                []
            )
        )

        publication_date = (
            attributes.get("published")
            or attributes.get("publicationYear")
        )

        if publication_date:
            publication_date = str(
                publication_date
            )

        return {
            "kind": str(
                types.get("resourceTypeGeneral")
                or types.get("resourceType")
                or "research object"
            ).lower(),
            "title": self._first_title(
                attributes.get("titles", [])
            ),
            "authors": self._creator_names(
                attributes.get("creators", [])
            ),
            "author_details": attributes.get(
                "creators",
                []
            ),
            "publication_date": publication_date,
            "publisher": attributes.get(
                "publisher"
            ),
            "licence_string": self._datacite_licence(
                rights
            ),
            "doi": (
                attributes.get("doi")
                or doi
            ),
            "url": (
                attributes.get("url")
                or f"https://doi.org/{doi}"
            ),
            "description": description,
            "keywords": self._datacite_subjects(
                attributes.get(
                    "subjects",
                    []
                )
            ),
            "version": attributes.get(
                "version"
            ),
            "files": [],
            "related_identifiers": attributes.get(
                "relatedIdentifiers",
                []
            ),
            "access_right": self._datacite_access_right(
                rights
            ),
            "embargo_date": None,
            "funding": attributes.get(
                "fundingReferences",
                []
            ),
            "source": "datacite",
            "fetch_status": "success",
            "metadata_machine_readable": True,
            "repository_api_available": True,
            "raw_text": description
        }

    def _fetch_crossref(self, doi):
        api_url = (
            f"https://api.crossref.org/works/"
            f"{doi}"
        )

        try:
            response = self.session.get(
                api_url,
                timeout=DEFAULT_TIMEOUT
            )

        except requests.RequestException:
            return None

        if not response.ok:
            return None

        try:
            message = response.json().get(
                "message",
                {}
            )

        except ValueError:
            return None

        if not message:
            return None

        description = self._clean_html(
            message.get("abstract")
        )

        return {
            "kind": str(
                message.get("type")
                or "publication"
            ).lower(),
            "title": self._first_list_value(
                message.get("title")
            ),
            "authors": self._crossref_author_names(
                message.get("author", [])
            ),
            "author_details": message.get(
                "author",
                []
            ),
            "publication_date": self._crossref_date(
                message
            ),
            "publisher": message.get(
                "publisher"
            ),
            "licence_string": self._crossref_licence(
                message.get("license", [])
            ),
            "doi": (
                message.get("DOI")
                or doi
            ),
            "url": (
                message.get("URL")
                or f"https://doi.org/{doi}"
            ),
            "description": description,
            "keywords": message.get(
                "subject",
                []
            ),
            "version": None,
            "files": [],
            "related_identifiers": message.get(
                "relation",
                {}
            ),
            "access_right": None,
            "embargo_date": None,
            "funding": message.get(
                "funder",
                []
            ),
            "source": "crossref",
            "fetch_status": "success",
            "metadata_machine_readable": True,
            "repository_api_available": True,
            "raw_text": description
        }

    def _fetch_webpage(self, url):
        try:
            response = self.session.get(
                url,
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True
            )

        except requests.RequestException as error:
            return self._empty_record(
                f"Webpage request failed: {error}",
                url=url
            )

        if not response.ok:
            return self._empty_record(
                (
                    f"Webpage returned HTTP "
                    f"{response.status_code}."
                ),
                url=url
            )

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if "html" not in content_type:
            return {
                **self._empty_record(
                    (
                        "The resource is reachable, "
                        "but no HTML metadata was available."
                    ),
                    url=response.url
                ),
                "kind": "digital resource",
                "fetch_status": "success",
                "access_right": "open"
            }

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        title = self._meta_value(
            soup,
            [
                "citation_title",
                "dc.title",
                "dcterms.title",
                "og:title"
            ]
        )

        if not title and soup.title:
            title = soup.title.get_text(
                " ",
                strip=True
            )

        authors = self._meta_values(
            soup,
            [
                "citation_author",
                "dc.creator",
                "dcterms.creator",
                "author"
            ]
        )

        publication_date = self._meta_value(
            soup,
            [
                "citation_publication_date",
                "citation_date",
                "dc.date",
                "dcterms.date",
                "article:published_time"
            ]
        )

        publisher = self._meta_value(
            soup,
            [
                "citation_publisher",
                "dc.publisher",
                "dcterms.publisher"
            ]
        )

        description = self._meta_value(
            soup,
            [
                "citation_abstract",
                "dc.description",
                "dcterms.description",
                "description",
                "og:description"
            ]
        )

        doi_value = self._meta_value(
            soup,
            [
                "citation_doi",
                "dc.identifier",
                "dcterms.identifier"
            ]
        )

        doi = self._find_doi(
            doi_value
            or response.text
        )

        keywords = self._meta_values(
            soup,
            [
                "citation_keywords",
                "dc.subject",
                "dcterms.subject",
                "keywords"
            ]
        )

        return {
            "kind": "webpage",
            "title": title,
            "authors": authors,
            "author_details": [],
            "publication_date": publication_date,
            "publisher": publisher,
            "licence_string": self._extract_page_licence(
                soup,
                response.text
            ),
            "doi": doi,
            "url": response.url,
            "description": self._clean_html(
                description
            ),
            "keywords": keywords,
            "version": None,
            "files": [],
            "related_identifiers": [],
            "access_right": "open",
            "embargo_date": None,
            "funding": [],
            "source": "html_metadata",
            "fetch_status": "success",
            "metadata_machine_readable": bool(doi),
            "repository_api_available": False,
            "raw_text": self._clean_html(
                description
            )
        }

    def _parse_free_text(self, text):
        return {
            "kind": "text",
            "title": None,
            "authors": [],
            "author_details": [],
            "publication_date": None,
            "publisher": None,
            "licence_string": self._find_licence_in_text(
                text
            ),
            "doi": self._find_doi(text),
            "url": None,
            "description": text[:5000],
            "keywords": [],
            "version": None,
            "files": [],
            "related_identifiers": [],
            "access_right": None,
            "embargo_date": None,
            "funding": [],
            "source": "user_input",
            "fetch_status": "not_requested",
            "metadata_machine_readable": False,
            "repository_api_available": False,
            "raw_text": text[:5000]
        }

    def _empty_record(self, note, **extra):
        record = {
            "kind": "unknown",
            "title": None,
            "authors": [],
            "author_details": [],
            "publication_date": None,
            "publisher": None,
            "licence_string": None,
            "doi": None,
            "url": None,
            "description": "",
            "keywords": [],
            "version": None,
            "files": [],
            "related_identifiers": [],
            "access_right": None,
            "embargo_date": None,
            "funding": [],
            "source": "none",
            "fetch_status": "failed",
            "metadata_machine_readable": False,
            "repository_api_available": False,
            "raw_text": "",
            "note": note
        }

        record.update(extra)

        return record

    def _find_doi(self, text):
        match = DOI_PATTERN.search(
            str(text or "")
        )

        if not match:
            return None

        return match.group(0).rstrip(
            ".,;:)]}"
        )

    def _find_zenodo_id(self, text):
        match = ZENODO_PATTERN.search(
            str(text or "")
        )

        return match.group(1) if match else None

    def _resource_type(self, value):
        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            return (
                value.get("type")
                or value.get("title")
                or "research object"
            )

        return "research object"

    def _licence_value(self, value):
        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            return (
                value.get("id")
                or value.get("title")
                or value.get("url")
            )

        return None

    def _creator_names(self, creators):
        names = []

        for creator in creators or []:
            if isinstance(creator, str):
                name = creator

            else:
                name = creator.get("name")

                if not name:
                    name = " ".join(filter(
                        None,
                        [
                            (
                                creator.get("givenName")
                                or creator.get("given")
                            ),
                            (
                                creator.get("familyName")
                                or creator.get("family")
                            )
                        ]
                    ))

            if name:
                names.append(
                    str(name).strip()
                )

        return names

    def _crossref_author_names(self, authors):
        names = []

        for author in authors or []:
            name = " ".join(filter(
                None,
                [
                    author.get("given"),
                    author.get("family")
                ]
            )).strip()

            if name:
                names.append(name)

        return names

    def _normalise_zenodo_files(self, files):
        normalised = []

        for item in files or []:
            links = item.get(
                "links",
                {}
            )

            normalised.append({
                "name": (
                    item.get("key")
                    or item.get("filename")
                ),
                "size": item.get("size"),
                "checksum": item.get("checksum"),
                "mime_type": (
                    item.get("type")
                    or item.get("mimetype")
                ),
                "download_url": (
                    links.get("self")
                    or links.get("download")
                )
            })

        return normalised

    def _first_title(self, titles):
        for item in titles or []:
            if isinstance(item, str):
                if item.strip():
                    return item.strip()

            elif item.get("title"):
                return item["title"].strip()

        return None

    def _first_description(self, descriptions):
        for item in descriptions or []:
            description = self._clean_html(
                item.get("description")
            )

            if description:
                return description

        return ""

    def _datacite_licence(self, rights):
        for item in rights or []:
            value = (
                item.get("rightsIdentifier")
                or item.get("rightsUri")
                or item.get("rights")
            )

            if value:
                return value

        return None

    def _datacite_access_right(self, rights):
        rights_text = " ".join(
            str(
                item.get("rights")
                or item.get("rightsIdentifier")
                or ""
            )
            for item in rights or []
        ).lower()

        if "open access" in rights_text:
            return "open"

        if "restricted" in rights_text:
            return "restricted"

        return None

    def _datacite_subjects(self, subjects):
        values = []

        for item in subjects or []:
            if isinstance(item, str):
                value = item
            else:
                value = item.get("subject")

            if value:
                values.append(value)

        return values

    def _crossref_date(self, message):
        for key in (
            "published-print",
            "published-online",
            "issued",
            "created"
        ):
            date_parts = (
                message.get(key)
                or {}
            ).get(
                "date-parts",
                [[]]
            )

            if date_parts and date_parts[0]:
                return "-".join(
                    str(part).zfill(2)
                    for part in date_parts[0]
                )

        return None

    def _crossref_licence(self, licences):
        for item in licences or []:
            value = (
                item.get("URL")
                or item.get("url")
            )

            if value:
                return value

        return None

    def _first_list_value(self, value):
        if isinstance(value, list):
            return value[0] if value else None

        return value

    def _clean_html(self, value):
        if not value:
            return ""

        soup = BeautifulSoup(
            str(value),
            "html.parser"
        )

        return unescape(
            soup.get_text(
                " ",
                strip=True
            )
        )

    def _meta_value(self, soup, names):
        values = self._meta_values(
            soup,
            names
        )

        return values[0] if values else None

    def _meta_values(self, soup, names):
        accepted_names = {
            name.lower()
            for name in names
        }

        values = []

        for tag in soup.find_all("meta"):
            key = str(
                tag.get("name")
                or tag.get("property")
                or tag.get("itemprop")
                or ""
            ).lower()

            if key not in accepted_names:
                continue

            value = tag.get("content")

            if (
                value
                and value.strip()
                and value.strip() not in values
            ):
                values.append(
                    value.strip()
                )

        return values

    def _extract_page_licence(
        self,
        soup,
        html
    ):
        licence_link = soup.find(
            "link",
            rel=lambda value: (
                value
                and "license" in value
            )
        )

        if (
            licence_link
            and licence_link.get("href")
        ):
            return licence_link["href"]

        return self._find_licence_in_text(
            html
        )

    def _find_licence_in_text(self, text):
        patterns = [
            r"\bCC0(?:[-\s]?1\.0)?\b",
            (
                r"\bCC[-\s]?BY[-\s]?NC[-\s]?ND"
                r"(?:[-\s]?4\.0)?\b"
            ),
            (
                r"\bCC[-\s]?BY[-\s]?NC[-\s]?SA"
                r"(?:[-\s]?4\.0)?\b"
            ),
            (
                r"\bCC[-\s]?BY[-\s]?NC"
                r"(?:[-\s]?4\.0)?\b"
            ),
            (
                r"\bCC[-\s]?BY[-\s]?ND"
                r"(?:[-\s]?4\.0)?\b"
            ),
            (
                r"\bCC[-\s]?BY[-\s]?SA"
                r"(?:[-\s]?4\.0)?\b"
            ),
            (
                r"\bCC[-\s]?BY"
                r"(?:[-\s]?4\.0)?\b"
            ),
            r"\bMIT License\b",
            (
                r"\bApache License"
                r"(?:,? Version)? 2\.0\b"
            ),
            r"\bGPL[-\s]?(?:v)?[23](?:\.0)?\b",
            r"\bAll Rights Reserved\b"
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                str(text or ""),
                re.IGNORECASE
            )

            if match:
                return match.group(0)

        return None