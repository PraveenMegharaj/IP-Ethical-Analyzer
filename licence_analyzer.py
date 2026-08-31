import re


LICENCE_TABLE = {
    "CC0-1.0": {
        "name": "CC0 1.0 Universal",
        "family": "creative_commons",
        "openness": 100,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": False,
        "share_alike": False
    },
    "CC-BY-4.0": {
        "name": "Creative Commons Attribution 4.0",
        "family": "creative_commons",
        "openness": 90,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "CC-BY-SA-4.0": {
        "name": "Creative Commons Attribution-ShareAlike 4.0",
        "family": "creative_commons",
        "openness": 78,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": True
    },
    "CC-BY-NC-4.0": {
        "name": "Creative Commons Attribution-NonCommercial 4.0",
        "family": "creative_commons",
        "openness": 55,
        "commercial": False,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "CC-BY-ND-4.0": {
        "name": "Creative Commons Attribution-NoDerivatives 4.0",
        "family": "creative_commons",
        "openness": 45,
        "commercial": True,
        "adaptations": False,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "CC-BY-NC-SA-4.0": {
        "name": "Creative Commons Attribution-NonCommercial-ShareAlike 4.0",
        "family": "creative_commons",
        "openness": 48,
        "commercial": False,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": True
    },
    "CC-BY-NC-ND-4.0": {
        "name": "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0",
        "family": "creative_commons",
        "openness": 30,
        "commercial": False,
        "adaptations": False,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "MIT": {
        "name": "MIT License",
        "family": "permissive_software",
        "openness": 95,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "Apache-2.0": {
        "name": "Apache License 2.0",
        "family": "permissive_software",
        "openness": 95,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "BSD-3-Clause": {
        "name": "BSD 3-Clause License",
        "family": "permissive_software",
        "openness": 95,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "GPL-3.0-only": {
        "name": "GNU General Public License v3.0",
        "family": "copyleft_software",
        "openness": 75,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": True
    },
    "GPL-2.0-only": {
        "name": "GNU General Public License v2.0",
        "family": "copyleft_software",
        "openness": 75,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": True
    },
    "AGPL-3.0-only": {
        "name": "GNU Affero General Public License v3.0",
        "family": "copyleft_software",
        "openness": 70,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": True
    },
    "ODC-BY-1.0": {
        "name": "Open Data Commons Attribution License 1.0",
        "family": "open_data",
        "openness": 88,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": False
    },
    "ODbL-1.0": {
        "name": "Open Data Commons Open Database License 1.0",
        "family": "open_data",
        "openness": 75,
        "commercial": True,
        "adaptations": True,
        "redistribution": True,
        "attribution": True,
        "share_alike": True
    },
    "Proprietary": {
        "name": "Proprietary / All Rights Reserved",
        "family": "closed",
        "openness": 10,
        "commercial": False,
        "adaptations": False,
        "redistribution": False,
        "attribution": True,
        "share_alike": False
    }
}


NORMALISATION_RULES = [
    (
        r"creativecommons\.org/publicdomain/zero|"
        r"\bcc0(?:[-\s]?1\.0)?\b",
        "CC0-1.0"
    ),
    (
        r"creativecommons\.org/licenses/by-nc-nd|"
        r"\bcc[\s-]?by[\s-]?nc[\s-]?nd(?:[\s-]?4\.0)?\b",
        "CC-BY-NC-ND-4.0"
    ),
    (
        r"creativecommons\.org/licenses/by-nc-sa|"
        r"\bcc[\s-]?by[\s-]?nc[\s-]?sa(?:[\s-]?4\.0)?\b",
        "CC-BY-NC-SA-4.0"
    ),
    (
        r"creativecommons\.org/licenses/by-nc|"
        r"\bcc[\s-]?by[\s-]?nc(?:[\s-]?4\.0)?\b",
        "CC-BY-NC-4.0"
    ),
    (
        r"creativecommons\.org/licenses/by-nd|"
        r"\bcc[\s-]?by[\s-]?nd(?:[\s-]?4\.0)?\b",
        "CC-BY-ND-4.0"
    ),
    (
        r"creativecommons\.org/licenses/by-sa|"
        r"\bcc[\s-]?by[\s-]?sa(?:[\s-]?4\.0)?\b",
        "CC-BY-SA-4.0"
    ),
    (
        r"creativecommons\.org/licenses/by|"
        r"\bcc[\s-]?by(?:[\s-]?4\.0)?\b",
        "CC-BY-4.0"
    ),
    (
        r"\bmit licen[cs]e\b|^mit$",
        "MIT"
    ),
    (
        r"\bapache(?: license)?[\s-]?2\.0\b",
        "Apache-2.0"
    ),
    (
        r"\bbsd[\s-]?3(?:[\s-]?clause)?\b",
        "BSD-3-Clause"
    ),
    (
        r"\bagpl(?:[\s-]?v)?[\s-]?3(?:\.0)?\b",
        "AGPL-3.0-only"
    ),
    (
        r"\bgpl(?:[\s-]?v)?[\s-]?3(?:\.0)?\b",
        "GPL-3.0-only"
    ),
    (
        r"\bgpl(?:[\s-]?v)?[\s-]?2(?:\.0)?\b",
        "GPL-2.0-only"
    ),
    (
        r"\bodc[\s-]?by(?:[\s-]?1\.0)?\b",
        "ODC-BY-1.0"
    ),
    (
        r"\bodbl(?:[\s-]?1\.0)?\b|"
        r"open database licen[cs]e",
        "ODbL-1.0"
    ),
    (
        r"\ball rights reserved\b|"
        r"\bproprietary\b|"
        r"\bclosed licen[cs]e\b",
        "Proprietary"
    )
]


class LicenceAnalyzer:
    def analyze(self, licence_input):
        if not licence_input:
            return self._unknown(
                status="missing",
                note=(
                    "No licence information was detected. "
                    "Reuse conditions are therefore unclear."
                )
            )

        raw = str(licence_input).strip()

        for spdx_id, details in LICENCE_TABLE.items():
            if raw.lower() == spdx_id.lower():
                return self._build_result(
                    spdx_id,
                    details,
                    raw
                )

        for pattern, spdx_id in NORMALISATION_RULES:
            if re.search(
                pattern,
                raw,
                re.IGNORECASE
            ):
                return self._build_result(
                    spdx_id,
                    LICENCE_TABLE[spdx_id],
                    raw
                )

        return self._unknown(
            raw=raw,
            status="unrecognised",
            note=(
                "A licence value was found, but it was not "
                "recognised by the current licence rules."
            )
        )

    def _build_result(
        self,
        spdx_id,
        details,
        raw
    ):
        result = {
            "detected": True,
            "status": "recognised",
            "raw_input": raw,
            "spdx_id": spdx_id,
            "name": details["name"],
            "family": details["family"],
            "openness": details["openness"],
            "commercial": details["commercial"],
            "adaptations": details["adaptations"],
            "redistribution": details["redistribution"],
            "attribution": details["attribution"],
            "share_alike": details["share_alike"],
            "ai_training": None,
            "ai_training_status": "requires_separate_review",
            "ai_training_note": (
                "The detected licence alone is not treated as "
                "conclusive permission for AI training. Privacy, "
                "contracts, database rights, sensitive data, and "
                "other restrictions may also apply."
            ),
            "plain_english": self._describe(
                details
            ),
            "disclaimer": (
                "This is an automated licence interpretation "
                "for decision support, not legal advice."
            )
        }

        return result

    def _describe(self, details):
        statements = []

        if details["commercial"] is True:
            statements.append(
                "commercial reuse is generally allowed"
            )
        elif details["commercial"] is False:
            statements.append(
                "commercial reuse is restricted"
            )

        if details["adaptations"] is True:
            statements.append(
                "adaptation is generally allowed"
            )
        elif details["adaptations"] is False:
            statements.append(
                "adapted versions are restricted"
            )

        if details["redistribution"] is True:
            statements.append(
                "redistribution is generally allowed"
            )
        elif details["redistribution"] is False:
            statements.append(
                "redistribution is restricted"
            )

        if details["attribution"]:
            statements.append(
                "attribution is required"
            )
        else:
            statements.append(
                "attribution is not required by this licence"
            )

        if details["share_alike"]:
            statements.append(
                "share-alike conditions apply"
            )

        return "; ".join(statements).capitalize() + "."

    def _unknown(
        self,
        raw=None,
        status="missing",
        note=None
    ):
        return {
            "detected": False,
            "status": status,
            "raw_input": raw,
            "spdx_id": None,
            "name": "Unknown or no licence detected",
            "family": None,
            "openness": None,
            "commercial": None,
            "adaptations": None,
            "redistribution": None,
            "attribution": None,
            "share_alike": None,
            "ai_training": None,
            "ai_training_status": "unknown",
            "ai_training_note": (
                "AI-training permission cannot be assessed "
                "because no recognised licence was found."
            ),
            "plain_english": note or (
                "Reuse conditions could not be determined."
            ),
            "disclaimer": (
                "The absence of a detected licence does not "
                "mean that the resource is free to reuse."
            )
        }