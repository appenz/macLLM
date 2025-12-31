import os
import pytest
from macllm.models.inception_connector import InceptionConnector


@pytest.mark.external
def test_inception_connector_real():
    if not os.getenv("INCEPTION_API_KEY"):
        pytest.skip("INCEPTION_API_KEY not set – skipping external tests")
    
    response, metadata = InceptionConnector.generate("Say hello", speed="normal")
    assert response is not None
    assert len(response.strip()) > 0
    assert metadata['provider'] == 'Inception'
    assert metadata['model'] == 'mercury'

