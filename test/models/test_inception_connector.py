import os
import pytest
from macllm.models.inception_connector import InceptionConnector


@pytest.mark.external
def test_inception_connector_real():
    if not os.getenv("INCEPTION_API_KEY"):
        pytest.skip("INCEPTION_API_KEY not set – skipping external tests")
    
    connector = InceptionConnector(model="mercury")
    response = connector.generate("Say hello")
    assert response is not None
    assert len(response.strip()) > 0

