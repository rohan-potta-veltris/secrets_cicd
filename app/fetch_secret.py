"""Fetch a secret from AWS Secrets Manager and demonstrate safe usage.

Reads SECRET_NAME and AWS_REGION from the environment, retrieves the secret
value from AWS Secrets Manager, and shows how to consume it without ever
logging, printing, or otherwise exposing the raw value.
"""
from __future__ import annotations

import json
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_secret(secret_name: str, region_name: str) -> dict:
    """Retrieve and parse a JSON secret from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        logger.error("Failed to retrieve secret '%s': %s", secret_name, code)
        raise

    return json.loads(response["SecretString"])


def mask(value: str, visible: int = 2) -> str:
    """Mask a sensitive string, keeping only a short visible prefix."""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


def use_secret(secret: dict, reveal: bool = False) -> None:
    """Demonstrate using the secret without exposing its raw value by default.

    `reveal` is an explicit, opt-in escape hatch for one-off manual
    verification (e.g. confirming the correct secret is being fetched while
    debugging OIDC/IAM setup) — it must never be left on for normal runs.
    """
    api_key = secret.get("demo_api_key")
    if not api_key:
        logger.error("Secret payload is missing the 'demo_api_key' field")
        sys.exit(1)

    if reveal:
        logger.warning(
            "SHOW_RAW_SECRET is enabled - printing the raw secret value. "
            "This is for one-off manual verification only; turn it off again."
        )
        logger.warning("Raw secret value: %s", api_key)

    logger.info("Retrieved secret (masked): %s (length=%d)", mask(api_key), len(api_key))
    logger.info("Pretending to call an external API with the secret... success!")


def main() -> None:
    secret_name = os.environ.get("SECRET_NAME")
    region_name = os.environ.get("AWS_REGION", "us-east-1")
    reveal = os.environ.get("SHOW_RAW_SECRET", "false").lower() == "true"

    if not secret_name:
        logger.error("SECRET_NAME environment variable is not set")
        sys.exit(1)

    secret = get_secret(secret_name, region_name)
    use_secret(secret, reveal=reveal)


if __name__ == "__main__":
    main()
