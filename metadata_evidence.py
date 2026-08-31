from urllib.parse import urlparse

class MetadataEvidenceEngine:
    """Create transparent checklist suggestions from retrieved metadata."""

    def evaluate(self, artefact, licence_result=None, fair_result=None):
        artefact = artefact or {}
        licence_result = licence_result or {}
        fair_result = fair_result or {}

        files = artefact.get("files") or []
        description = str(artefact.get("description") or "")
        file_names = [
            str(item.get("name") or "")
            for item in files
            if isinstance(item, dict)
        ]

        evidence = {
            "F1": self._value_check(
                "doi",
                artefact.get("doi"),
                "A persistent identifier was found."
            ),
            "F2_TITLE": self._value_check(
                "title",
                artefact.get("title"),
                "A title was found."
            ),
            "F2_CREATORS": self._list_check(
                "authors",
                artefact.get("authors"),
                "Creator information was found."
            ),
            "F2_KEYWORDS": self._list_check(
                "keywords",
                artefact.get("keywords"),
                "Keywords were found."
            ),
            "F4": self._repository_check(artefact),
            "A1": self._retrieval_check(artefact),
            "A1_PROTOCOL": self._protocol_check(
                artefact.get("url")
            ),
            "A1_CONDITIONS": self._value_check(
                "access_right",
                artefact.get("access_right"),
                "Access conditions were found."
            ),
            "A_RESTRICTED": self._restricted_access_check(
                artefact
            ),
            "A2": self._boolean_check(
                "repository_api_available",
                artefact.get("repository_api_available"),
                (
                    "A repository API or machine-readable "
                    "metadata endpoint was detected."
                )
            ),
            "I1": self._boolean_check(
                "metadata_machine_readable",
                artefact.get("metadata_machine_readable"),
                "Machine-readable metadata was detected."
            ),
            "I2": self._fair_vocabulary_check(
                fair_result
            ),
            "I_CREATOR_IDS": self._creator_identifier_check(
                artefact.get("author_details")
            ),
            "I3": self._list_check(
                "related_identifiers",
                artefact.get("related_identifiers"),
                "Related identifiers were found."
            ),
            "I_FORMATS": self._format_metadata_check(
                files
            ),
            "R1_LICENSE": self._licence_check(
                licence_result
            ),
            "R1_PROVENANCE": self._provenance_check(
                artefact
            ),
            "R1_VERSION": self._value_check(
                "version",
                artefact.get("version"),
                "A version was found."
            ),
            "R1_DESCRIPTION": self._text_check(
                "description",
                description,
                30,
                "A descriptive summary was found."
            ),
            "R1_LIMITATIONS": self._document_hint(
                description,
                file_names,
                [
                    "limitation",
                    "limitations",
                    "known issue",
                    "intended use"
                ],
                (
                    "A possible limitations or intended-use "
                    "statement was found."
                )
            ),
            "R1_STANDARDS": self._document_hint(
                description,
                file_names,
                [
                    "standard",
                    "schema",
                    "ontology",
                    "vocabulary"
                ],
                "A possible standards reference was found."
            ),
            "AI_MACHINE_READABLE": self._boolean_check(
                "metadata_machine_readable",
                artefact.get("metadata_machine_readable"),
                "The metadata can be processed programmatically."
            ),
            "AI_FORMAT": self._machine_format_check(
                files
            ),
            "AI_DOCUMENTATION": self._documentation_check(
                description,
                file_names
            ),
            "AI_SCHEMA": self._file_hint(
                file_names,
                [
                    "dictionary",
                    "schema",
                    "codebook",
                    "variables",
                    "columns"
                ],
                (
                    "A possible schema or data dictionary "
                    "file was found."
                )
            ),
            "AI_QUALITY": self._document_hint(
                description,
                file_names,
                [
                    "quality",
                    "validation",
                    "validated",
                    "quality control",
                    "qc"
                ],
                (
                    "A possible quality or validation "
                    "statement was found."
                )
            ),
            "AI_BIAS": self._document_hint(
                description,
                file_names,
                [
                    "bias",
                    "representative",
                    "representativeness",
                    "coverage"
                ],
                (
                    "A possible bias or representativeness "
                    "statement was found."
                )
            ),
            "AI_UPDATE": self._update_check(
                artefact
            ),
            "RL_LICENSE": self._licence_check(
                licence_result
            ),
            "RL_ATTRIBUTION": self._licence_condition_check(
                licence_result,
                "attribution",
                "Attribution requirements are identifiable."
            ),
            "RL_COMMERCIAL": self._licence_condition_check(
                licence_result,
                "commercial",
                "Commercial-use conditions are identifiable."
            ),
            "RL_ADAPTATION": self._licence_condition_check(
                licence_result,
                "adaptations",
                "Adaptation conditions are identifiable."
            )
        }

        return evidence

    def _result(
        self,
        answer,
        source,
        reason,
        evidence=None,
        confidence=1.0
    ):
        return {
            "suggested_answer": answer,
            "source": source,
            "reason": reason,
            "evidence": evidence or [],
            "confidence": round(float(confidence), 2)
        }

    def _value_check(self, field, value, reason):
        answer = (
            "yes"
            if value not in {None, ""}
            else "no"
        )

        evidence = (
            [{"field": field, "value": value}]
            if answer == "yes"
            else []
        )

        return self._result(
            answer,
            "repository_metadata",
            reason,
            evidence
        )

    def _list_check(self, field, values, reason):
        values = values or []
        answer = "yes" if values else "no"

        evidence = (
            [{"field": field, "value": values}]
            if values
            else []
        )

        return self._result(
            answer,
            "repository_metadata",
            reason,
            evidence
        )

    def _boolean_check(self, field, value, reason):
        if value is True:
            return self._result(
                "yes",
                "repository_metadata",
                reason,
                [{
                    "field": field,
                    "value": True
                }]
            )

        if value is False:
            return self._result(
                "no",
                "repository_metadata",
                reason,
                [{
                    "field": field,
                    "value": False
                }]
            )

        return self._result(
            "not_assessed",
            "repository_metadata",
            "No reliable metadata value was found."
        )

    def _repository_check(self, artefact):
        source = str(
            artefact.get("source")
            or ""
        ).lower()

        publisher = artefact.get(
            "publisher"
        )

        passed = (
            source in {
                "zenodo",
                "datacite",
                "crossref"
            }
            or bool(publisher)
        )

        evidence = [
            {
                "field": "source",
                "value": source
            },
            {
                "field": "publisher",
                "value": publisher
            }
        ]

        reason = (
            "A searchable repository or metadata "
            "service was detected."
            if passed
            else "No searchable repository was confirmed."
        )

        return self._result(
            "yes" if passed else "no",
            "repository_metadata",
            reason,
            evidence
        )

    def _retrieval_check(self, artefact):
        status = artefact.get(
            "fetch_status"
        )

        reason = (
            "The resource metadata was retrieved successfully."
            if status == "success"
            else "The resource could not be retrieved."
        )

        return self._result(
            "yes" if status == "success" else "no",
            "resource_retrieval",
            reason,
            [{
                "field": "fetch_status",
                "value": status
            }]
        )

    def _protocol_check(self, url):
        scheme = urlparse(
            str(url or "")
        ).scheme.lower()

        passed = scheme in {
            "http",
            "https"
        }

        reason = (
            "A standard web protocol was found."
            if passed
            else (
                "No standard retrieval protocol "
                "was confirmed."
            )
        )

        return self._result(
            "yes" if passed else "no",
            "resource_url",
            reason,
            [{
                "field": "url",
                "value": url
            }]
        )

    def _restricted_access_check(self, artefact):
        access = str(
            artefact.get("access_right")
            or ""
        ).strip().lower()

        if access in {
            "open",
            "open access",
            "public",
            "publicly available"
        }:
            return self._result(
                "not_applicable",
                "repository_metadata",
                (
                    "The dataset is openly accessible, so a "
                    "restricted-access procedure is not applicable."
                ),
                [{
                    "field": "access_right",
                    "value": access
                }]
            )

        if access in {
            "restricted",
            "controlled",
            "registration required",
            "embargoed",
            "embargo"
        }:
            return self._result(
                "not_assessed",
                "repository_metadata",
                (
                    "Restricted access was detected. The request "
                    "procedure needs human confirmation."
                ),
                [{
                    "field": "access_right",
                    "value": access
                }],
                confidence=0.5
            )

        return self._result(
            "not_assessed",
            "repository_metadata",
            "Access restrictions could not be determined.",
            confidence=0.0
        )

    def _fair_vocabulary_check(self, fair_result):
        value = (
            fair_result.get(
                "principles",
                {}
            ).get("I2")
        )

        if value is None:
            for metric in fair_result.get(
                "checks",
                []
            ):
                metric_id = str(
                    metric.get("id")
                    or ""
                )

                label = str(
                    metric.get("label")
                    or ""
                ).lower()

                if (
                    "I2" in metric_id
                    or "semantic" in label
                ):
                    value = metric.get(
                        "score_percent"
                    )
                    break

        if value is None:
            return self._result(
                "not_assessed",
                "f_uji",
                (
                    "F-UJI did not provide clear "
                    "vocabulary evidence."
                ),
                confidence=0.0
            )

        passed = float(value) >= 50

        return self._result(
            "yes" if passed else "no",
            "f_uji",
            (
                "F-UJI provided a signal about "
                "controlled vocabularies."
            ),
            [{
                "field": "F-UJI I2",
                "value": value
            }],
            confidence=0.75
        )

    def _creator_identifier_check(self, creators):
        creators = creators or []
        found = []

        for creator in creators:
            if not isinstance(creator, dict):
                continue

            value = (
                creator.get("orcid")
                or creator.get("identifier")
                or creator.get("nameIdentifiers")
            )

            if value:
                found.append(value)

        reason = (
            "Persistent creator identifiers were found."
            if found
            else (
                "No persistent creator identifier "
                "was found."
            )
        )

        evidence = (
            [{
                "field": "creator_identifiers",
                "value": found
            }]
            if found
            else []
        )

        return self._result(
            "yes" if found else "no",
            "repository_metadata",
            reason,
            evidence
        )

    def _format_metadata_check(self, files):
        formats = []

        for item in files or []:
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            mime_type = (
                item.get("mime_type")
                or item.get("type")
            )

            if name or mime_type:
                formats.append({
                    "name": name,
                    "mime_type": mime_type
                })

        reason = (
            "File names or formats were documented."
            if formats
            else (
                "No file-format information "
                "was found."
            )
        )

        return self._result(
            "yes" if formats else "no",
            "repository_metadata",
            reason,
            formats
        )

    def _licence_check(self, licence_result):
        detected = (
            licence_result.get("detected")
            is True
        )

        value = (
            licence_result.get("spdx_id")
            or licence_result.get("raw_input")
        )

        reason = (
            "A recognised licence was detected."
            if detected
            else "No recognised licence was detected."
        )

        evidence = (
            [{
                "field": "licence",
                "value": value
            }]
            if value
            else []
        )

        return self._result(
            "yes" if detected else "no",
            "licence_analyser",
            reason,
            evidence
        )

    def _licence_condition_check(
        self,
        licence_result,
        field,
        reason
    ):
        value = licence_result.get(
            field
        )

        identifiable = value is not None

        return self._result(
            (
                "yes"
                if identifiable
                else "not_assessed"
            ),
            "licence_analyser",
            (
                reason
                if identifiable
                else (
                    "The condition could not be determined "
                    "from the detected licence."
                )
            ),
            (
                [{
                    "field": field,
                    "value": value
                }]
                if identifiable
                else []
            )
        )

    def _provenance_check(self, artefact):
        evidence = []

        for field in (
            "publisher",
            "funding",
            "source"
        ):
            value = artefact.get(
                field
            )

            if value:
                evidence.append({
                    "field": field,
                    "value": value
                })

        reason = (
            "Basic provenance information was found."
            if evidence
            else "No provenance information was found."
        )

        return self._result(
            "yes" if evidence else "no",
            "repository_metadata",
            reason,
            evidence
        )

    def _text_check(
        self,
        field,
        text,
        minimum_words,
        reason
    ):
        words = str(
            text or ""
        ).split()

        passed = (
            len(words)
            >= minimum_words
        )

        evidence = (
            [{
                "field": field,
                "value": self._shorten(text)
            }]
            if text
            else []
        )

        return self._result(
            "yes" if passed else "no",
            "repository_metadata",
            (
                reason
                if passed
                else (
                    "The available description is too "
                    "limited for this check."
                )
            ),
            evidence,
            confidence=0.8
        )

    def _documentation_check(
        self,
        description,
        file_names
    ):
        readme = [
            name
            for name in file_names
            if "readme" in name.lower()
        ]

        enough_description = (
            len(description.split())
            >= 30
        )

        passed = (
            bool(readme)
            or enough_description
        )

        evidence = []

        if readme:
            evidence.append({
                "field": "files",
                "value": readme
            })

        if enough_description:
            evidence.append({
                "field": "description",
                "value": self._shorten(
                    description
                )
            })

        reason = (
            "Documentation evidence was found."
            if passed
            else (
                "No substantial README or "
                "description was found."
            )
        )

        return self._result(
            "yes" if passed else "no",
            "documentation_scan",
            reason,
            evidence,
            confidence=0.75
        )

    def _machine_format_check(self, files):
        extensions = (
            ".csv",
            ".tsv",
            ".json",
            ".jsonld",
            ".xml",
            ".rdf",
            ".ttl",
            ".parquet",
            ".h5",
            ".hdf5",
            ".zip"
        )

        matches = []

        for item in files or []:
            if not isinstance(item, dict):
                continue

            name = str(
                item.get("name")
                or ""
            ).lower()

            mime_type = str(
                item.get("mime_type")
                or item.get("type")
                or ""
            ).lower()

            mime_match = any(
                token in mime_type
                for token in (
                    "json",
                    "csv",
                    "xml",
                    "rdf",
                    "zip"
                )
            )

            if (
                name.endswith(extensions)
                or mime_match
            ):
                matches.append({
                    "name": item.get("name"),
                    "mime_type": mime_type
                })

        reason = (
            "Machine-processable files were found."
            if matches
            else (
                "No clearly machine-processable "
                "file format was found."
            )
        )

        return self._result(
            "yes" if matches else "no",
            "file_format_scan",
            reason,
            matches,
            confidence=0.8
        )

    def _file_hint(
        self,
        file_names,
        keywords,
        reason
    ):
        matches = [
            name
            for name in file_names
            if any(
                keyword in name.lower()
                for keyword in keywords
            )
        ]

        if not matches:
            return self._result(
                "not_assessed",
                "documentation_scan",
                "No clear supporting file was found.",
                confidence=0.0
            )

        return self._result(
            "yes",
            "documentation_scan",
            reason,
            [{
                "field": "files",
                "value": matches
            }],
            confidence=0.65
        )

    def _document_hint(
        self,
        description,
        file_names,
        keywords,
        reason
    ):
        text = description.lower()

        description_matches = [
            keyword
            for keyword in keywords
            if keyword in text
        ]

        file_matches = [
            name
            for name in file_names
            if any(
                keyword in name.lower()
                for keyword in keywords
            )
        ]

        evidence = []

        if description_matches:
            evidence.append({
                "field": "description_terms",
                "value": description_matches
            })

        if file_matches:
            evidence.append({
                "field": "files",
                "value": file_matches
            })

        if not evidence:
            return self._result(
                "not_assessed",
                "documentation_scan",
                (
                    "No clear evidence was found. "
                    "Human review is required."
                ),
                confidence=0.0
            )

        return self._result(
            "yes",
            "documentation_scan",
            reason,
            evidence,
            confidence=0.6
        )

    def _update_check(self, artefact):
        evidence = []

        if artefact.get("version"):
            evidence.append({
                "field": "version",
                "value": artefact.get("version")
            })

        if artefact.get("publication_date"):
            evidence.append({
                "field": "publication_date",
                "value": artefact.get(
                    "publication_date"
                )
            })

        reason = (
            "Version or date information was found."
            if evidence
            else (
                "No version or date information "
                "was found."
            )
        )

        return self._result(
            "yes" if evidence else "no",
            "repository_metadata",
            reason,
            evidence
        )

    def _shorten(self, value, limit=240):
        text = str(
            value or ""
        ).strip()

        if len(text) <= limit:
            return text

        return f"{text[:limit].rstrip()}..."