import json

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from fetch_secret import get_secret, mask, use_secret

REGION = "us-east-1"
SECRET_NAME = "cicd-demo/api-key"
SECRET_VALUE = "super-secret-value-123"


@pytest.fixture
def secretsmanager_client():
    with mock_aws():
        client = boto3.client("secretsmanager", region_name=REGION)
        client.create_secret(
            Name=SECRET_NAME,
            SecretString=json.dumps({"demo_api_key": SECRET_VALUE}),
        )
        yield client


def test_get_secret_returns_parsed_json(secretsmanager_client):
    secret = get_secret(SECRET_NAME, REGION)
    assert secret == {"demo_api_key": SECRET_VALUE}


def test_get_secret_raises_for_missing_secret(secretsmanager_client):
    with pytest.raises(ClientError):
        get_secret("does-not-exist", REGION)


def test_mask_hides_all_but_prefix():
    assert mask(SECRET_VALUE) == "su" + "*" * (len(SECRET_VALUE) - 2)


def test_mask_short_value_fully_masked():
    assert mask("ab") == "**"


def test_use_secret_logs_without_raising(caplog):
    use_secret({"demo_api_key": SECRET_VALUE})
    assert SECRET_VALUE not in caplog.text


def test_use_secret_exits_when_key_missing():
    with pytest.raises(SystemExit):
        use_secret({})
