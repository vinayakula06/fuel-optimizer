import pytest
import httpx
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from apps.routing.geocoder import NominatimGeocoder
from apps.routing.client import OSRMClient

class TestGeocoder(TestCase):
    def setUp(self):
        cache.clear()

    @patch("httpx.get")
    def test_geocode_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"lat": "34.0522", "lon": "-118.2437"}]
        mock_get.return_value = mock_resp

        res = NominatimGeocoder.geocode("Los Angeles", "CA")
        self.assertEqual(res, (34.0522, -118.2437))
        mock_get.assert_called_once()

        # Cache hit
        mock_get.reset_mock()
        res_cached = NominatimGeocoder.geocode("Los Angeles", "CA")
        self.assertEqual(res_cached, (34.0522, -118.2437))
        mock_get.assert_not_called()

    @patch("httpx.get")
    def test_geocode_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        res = NominatimGeocoder.geocode("Unknown", "XX")
        self.assertIsNone(res)

    @patch("httpx.get")
    def test_geocode_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        res = NominatimGeocoder.geocode("Error", "ER")
        self.assertIsNone(res)

    @patch("httpx.get")
    def test_geocode_exception(self, mock_get):
        mock_get.side_effect = httpx.RequestError("Network down")
        res = NominatimGeocoder.geocode("Error", "ER")
        self.assertIsNone(res)


class TestOSRMClient(TestCase):
    def setUp(self):
        cache.clear()

    @patch("httpx.get")
    def test_get_route_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"routes": [{"distance": 100}]}
        mock_get.return_value = mock_resp

        res = OSRMClient.get_route(34.0, -118.0, 35.0, -119.0)
        self.assertEqual(res, {"routes": [{"distance": 100}]})
        mock_get.assert_called_once()

        # Cache hit
        mock_get.reset_mock()
        res_cached = OSRMClient.get_route(34.0, -118.0, 35.0, -119.0)
        self.assertEqual(res_cached, {"routes": [{"distance": 100}]})
        mock_get.assert_not_called()

    @patch("httpx.get")
    @patch("time.sleep")
    def test_get_route_retry_on_500(self, mock_sleep, mock_get):
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"routes": []}

        mock_get.side_effect = [mock_resp_500, mock_resp_200]

        res = OSRMClient.get_route(34.0, -118.0, 35.0, -119.0)
        self.assertEqual(res, {"routes": []})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)

    @patch("httpx.get")
    @patch("time.sleep")
    def test_get_route_fail_after_retries(self, mock_sleep, mock_get):
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.text = "Internal Server Error"
        mock_get.return_value = mock_resp_500

        res = OSRMClient.get_route(34.0, -118.0, 35.0, -119.0)
        self.assertIsNone(res)
        self.assertEqual(mock_get.call_count, 2)

    @patch("httpx.get")
    @patch("time.sleep")
    def test_get_route_exception_retry_and_raise(self, mock_sleep, mock_get):
        mock_get.side_effect = httpx.RequestError("Timeout")

        with self.assertRaises(httpx.RequestError):
            OSRMClient.get_route(34.0, -118.0, 35.0, -119.0)

        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)
