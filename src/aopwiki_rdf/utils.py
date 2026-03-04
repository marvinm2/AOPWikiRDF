"""Shared helper functions for the AOP-Wiki RDF pipeline.

Extracted from AOP-Wiki_XML_to_RDF_conversion.py (lines 46-280).
No module-level side effects. No logging.basicConfig(). No network calls.
"""

import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

# --- Constants / Compiled Patterns ---
TAG_RE = re.compile(r'<[^>]+>')
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')


def safe_get_text(element, default=''):
    """Safely extract text from XML element, returning default if None."""
    if element is not None and element.text is not None:
        return element.text.strip()
    return default


def clean_html_tags(text):
    """Remove HTML tags from text."""
    if text:
        return HTML_TAG_PATTERN.sub('', text)
    return text


def download_with_retry(url, filename, max_retries=3, timeout=30):
    """Download file with retry logic.

    Parameters are explicit (no module-level globals).
    Uses verify=False matching production behavior.
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading {url} (attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, verify=False, timeout=timeout)
            response.raise_for_status()

            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"Successfully downloaded {filename}")
            return True

        except requests.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to download {url} after {max_retries} attempts")
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    return False


def validate_xml_structure(root, expected_namespace):
    """Validate basic XML structure."""
    if root is None:
        raise ValueError("XML root is None")

    if root.tag != expected_namespace + 'data':
        logger.warning(f"Unexpected root tag: {root.tag}")

    vendor_section = root.find(expected_namespace + 'vendor-specific')
    if vendor_section is None:
        raise ValueError("Missing vendor-specific section in XML")

    logger.info("XML structure validation passed")
    return True


def validate_entity_counts(refs):
    """Validate that we have reasonable entity counts."""
    min_expected = {'AOP': 1, 'KE': 1, 'KER': 1, 'Stressor': 1}

    for entity_type, min_count in min_expected.items():
        actual_count = len(refs.get(entity_type, {}))
        if actual_count < min_count:
            logger.warning(f"Low count for {entity_type}: {actual_count} (expected >= {min_count})")
        else:
            logger.info(f"Entity count validation passed for {entity_type}: {actual_count}")

    return True


def validate_required_fields(entity_dict, entity_type, required_fields):
    """Validate that required fields are present in entities."""
    missing_fields = []
    for entity_id, entity_data in entity_dict.items():
        for fld in required_fields:
            if fld not in entity_data or not entity_data[fld]:
                missing_fields.append(f"{entity_type} {entity_id} missing {fld}")

    if missing_fields:
        logger.warning(f"Found {len(missing_fields)} missing required fields")
        for missing in missing_fields[:5]:
            logger.warning(missing)
        if len(missing_fields) > 5:
            logger.warning(f"... and {len(missing_fields) - 5} more")
    else:
        logger.info(f"Required field validation passed for {entity_type}")

    return len(missing_fields) == 0


def convert_lists_to_sets_for_lookup(dict_of_lists):
    """Convert dictionary of lists to sets for O(1) membership testing."""
    return {key: set(values) for key, values in dict_of_lists.items()}


def convert_sets_to_lists_for_output(dict_of_sets):
    """Convert dictionary of sets back to lists for consistent output format."""
    return {key: list(values) for key, values in dict_of_sets.items()}
