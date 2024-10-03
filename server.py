import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from urllib.parse import parse_qs, urlparse
import json
import pandas as pd
from datetime import datetime
import uuid
import os
from typing import Callable, Any
from wsgiref.simple_server import make_server

nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('stopwords', quiet=True)

adj_noun_pairs_count = {}
sia = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

reviews = pd.read_csv('data/reviews.csv').to_dict('records')


class ReviewAnalyzerServer:
    def __init__(self) -> None:
        # This method is a placeholder for future initialization logic
        pass

    def analyze_sentiment(self, review_body):
        sentiment_scores = sia.polarity_scores(review_body)
        return sentiment_scores

    def get_compound_sentiment(self, dict_obj):
        return dict_obj['sentiment']['compound']

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> bytes:
        """
        The environ parameter is a dictionary containing some useful
        HTTP request information such as: REQUEST_METHOD, CONTENT_LENGTH, QUERY_STRING,
        PATH_INFO, CONTENT_TYPE, etc.
        """

        existing_locations = [item['Location'] for item in reviews]
        if environ["REQUEST_METHOD"] == "GET":
            # Create the response body from the reviews and convert to a JSON byte string
            response_body = json.dumps(reviews, indent=2).encode("utf-8")

            # Write your code here
            try:
                query_params = parse_qs(environ['QUERY_STRING'])
                location = ''
                start_date = ''
                end_date = ''
                filtered_response = []

                if 'location' in environ['QUERY_STRING']:
                    location = query_params['location'][0]
                    if location in existing_locations:
                        filtered_response = [
                            data for data in reviews if data['Location'] == location]
                    else:
                        raise Exception('Invalid Location')

                if 'start_date' in environ['QUERY_STRING']:
                    start_date = query_params['start_date'][0]
                    if len(filtered_response) > 1:
                        temp = [
                            data for data in filtered_response if data['Timestamp'] >= start_date]
                        filtered_response = temp
                    else:
                        filtered_response = [
                            data for data in reviews if data['Timestamp'] >= start_date]

                if 'end_date' in environ['QUERY_STRING']:
                    end_date = query_params['end_date'][0]
                    if len(filtered_response) > 1:
                        temp = [
                            data for data in filtered_response if data['Timestamp'] <= end_date]
                        filtered_response = temp
                    else:
                        filtered_response = [
                            data for data in reviews if data['Timestamp'] <= end_date]

                # handle when no query params are present
                if len(query_params) < 1:
                    filtered_response = reviews

                for index, val in enumerate(filtered_response):
                    sentiments = self.analyze_sentiment(val['ReviewBody'])
                    filtered_response[index]['sentiment'] = sentiments

                # sort based on setntiment compund desc
                filtered_response.sort(
                    key=self.get_compound_sentiment, reverse=True)

                response_body = json.dumps(
                    filtered_response, indent=2).encode("utf-8")

                # Set the appropriate response headers
                start_response("200 OK", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(response_body)))
                ])

                return [response_body]

            except Exception as e:
                if str(e) == "Invalid Location":
                    status = '400 Bad Request'
                    headers = [('Content-Type', 'text/plain')]
                    start_response(status, headers)
                    return [b'Invalid Location']
                else:
                    status = '500 Internal Server Error'
                    headers = [('Content-Type', 'text/plain')]
                    start_response(status, headers)
                    return [b'internal server error occured']

        if environ["REQUEST_METHOD"] == "POST":
            # Write your code here
            try:
                try:
                    request_body_size = int(environ.get('CONTENT_LENGTH', 0))
                except (ValueError):
                    request_body_size = 0

                request_body = environ['wsgi.input'].read(request_body_size)
                pasrsed_request = parse_qs(request_body.decode())

                request_keys = pasrsed_request.keys()

                if 'Location' in request_keys and 'ReviewBody' in request_keys and pasrsed_request['Location'][0] in existing_locations:
                    location = pasrsed_request.get('Location')[0]
                    review_body = pasrsed_request.get('ReviewBody')[0]
                    review_id = str(uuid.uuid4())
                    timestamp = datetime.now()
                    formatted_timestamp = timestamp.strftime(
                        '%Y-%m-%d %H:%M:%S.%f'
                    )[:-7]
                    response_dict = {"ReviewId": review_id, "ReviewBody": review_body,
                                     "Location": location, "Timestamp": formatted_timestamp}
                    response_body = json.dumps(
                        response_dict, indent=2).encode("utf-8")

                    # Set the appropriate response headers
                    start_response("201 Created", [
                        ("Content-Type", "application/json"),
                        ("Content-Length", str(len(response_body)))
                    ])

                    return [response_body]
                else:
                    if 'Location' not in request_keys:
                        status = '400 Bad Request'
                        headers = [('Content-Type', 'text/plain')]
                        start_response(status, headers)
                        return [b'Missing Location']
                    if 'ReviewBody' not in request_keys:
                        status = '400 Bad Request'
                        headers = [('Content-Type', 'text/plain')]
                        start_response(status, headers)
                        return [b'Missing ReviewBody']
                    if pasrsed_request['Location'][0] not in existing_locations:
                        status = '400 Bad Request'
                        headers = [('Content-Type', 'text/plain')]
                        start_response(status, headers)
                        return [b'invalid Location']

            except Exception as e:
                status = '500 Internal Server Error'
                headers = [('Content-Type', 'text/plain')]
                start_response(status, headers)
                return [b'internal server error occured']


if __name__ == "__main__":
    app = ReviewAnalyzerServer()
    port = os.environ.get('PORT', 8000)
    with make_server("", port, app) as httpd:
        print(f"Listening on port {port}...")
        httpd.serve_forever()
