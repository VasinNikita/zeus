"""
Welcome to Zeus: script for complex and overloaded operations for Yandex Delivery API

Files to make things better:
    claims – \n separated file with claims to take action on
    token.json - JSON dictionary with 'clients' key which contains tokens of our clients

Available commands:
    accept - accepts claims by claim_id or external_order_ids[] in claims file
    [cancel, cancel_free, cancel_paid] - forces cancellation of claims free, paid or both

    reorder - reorders given claims by claim_id or external_order_id as SDD or Express orders
    save - creates a multi-stop order with claims given in claims file
    duplicates - finds duplicates with same external_order_id
    reversed - accepts claims or external_order_ids[] and reorders them
    report - generates a report for the given client based for a given date
    sorting_file - generates a CSV sorting_couriers file with route_id-external_order_id pair for active claims
    scanned - find parcels which were scanned with the sorting_couriers app
    claims - find claims based on external_order_id or request_id
    flush - output buffer

    find - finds claims based on params:
        × express or sdd strictly
        × same_day_data interval 'from'
        × pickup location
        × status[]

Available options for commands:
    -sandbox - use sandbox for requests
    -json - output json responses on screen for each request
    -trace - output Ya-Trace-ID for each request
    -logapi - change the API to LogAPI
    -express - change the API to Express
    -test - use the test host of a Delivery
"""
import copy
import datetime
import inspect
import random
import socket
import traceback
from copy import deepcopy

import requests
import xlsxwriter
import http.client
import json
import asyncio
import httpx
import ssl
import time

import pandas as pd
from dataclasses import dataclass
from secrets import token_hex
from typing import Optional
from colorama import init, Fore, Style
from tenacity import retry, retry_if_exception_type

raw_data = []
raw_data_express = []


async def main():
    max_concurrent_workers = 32
    semaphore = asyncio.Semaphore(max_concurrent_workers)

    addresses = {
        "test_location": "Moscow, Red Square, 1"
    }

    STAFF_TOKEN = ""

    try:
        STAFF_TOKEN = open("staff_token", "r").read()
    except Exception:
        pass

    try:

        class TempData:
            def __init__(self):
                self.claims = []

        class Actions:
            ACCEPT = "accept"
            CANCEL = "cancel"
            CANCEL_FREE = "cancel_free"
            CANCEL_PAID = "cancel_paid"
            REORDER = "reorder"
            SAVE = "save"
            DUPLICATES = "duplicates"
            REVERSED = "reversed"
            REPORT = "report"
            SORTING_FILE = "sorting_file"
            FIND = "find"
            CLAIMS = "claims"
            SCANNED = "scanned"
            FLUSH = "flush"
            COUNT = "count"
            HELP = "help"
            CREATE = "create"

        @dataclass(unsafe_hash=True)
        class Statuses:
            NEW = "new"
            ESTIMATING = "estimating"
            ESTIMATING_FAILED = "estimating_failed"
            READY_FOR_APPROVAL = "ready_for_approval"
            FAILED = "failed"
            ACCEPTED = "accepted"
            PERFORMER_LOOKUP = "performer_lookup"
            PERFORMER_DRAFT = "performer_draft"
            PERFORMER_FOUND = "performer_found"
            PERFORMER_NOT_FOUND = "performer_not_found"
            CANCELLED_BY_TAXI = "cancelled_by_taxi"
            PICKUP_ARRIVED = "pickup_arrived"
            READY_FOR_PICKUP_CONFIRMATION = "ready_for_pickup_confirmation"
            PICKUPED = "pickuped"
            DELIVERY_ARRIVED = "delivery_arrived"
            PAY_WAITING = "pay_waiting"
            READY_FOR_DELIVERY_CONFIRMATION = "ready_for_delivery_confirmation"
            DELIVERED = "delivered"
            DELIVERED_FINISH = "delivered_finish"
            RETURNING = "returning"
            RETURN_ARRIVED = "return_arrived"
            READY_FOR_RETURN_CONFIRMATION = "ready_for_return_confirmation"
            RETURNED_FINISH = "returned_finish"
            CANCELLED = "cancelled"
            CANCELLED_WITH_PAYMENT = "cancelled_with_payment"
            CANCELLED_WITH_ITEMS_ON_HANDS = "cancelled_with_items_on_hands"

            ROUTED = ["performer_draft", "performer_found", "pickup_arrived"]
            FINAL = ["estimating_failed", "failed", "performer_not_found", "cancelled_by_taxi", "delivered",
                     "delivered_finish",
                     "returned_finish", "cancelled", "cancelled_with_items_on_hands", "cancelled_with_payment"]
            FINAL_SUCCESS = ["delivered", "delivered_finish"]
            FINAL_RETURN = ["returned_finish"]

            @staticmethod
            def all_statuses():
                return [item[1] for item in Statuses.__dict__.items() if '_' not in item]

        class Express:
            HOST = "b2b.taxi.yandex.net"
            HOST_TEST = "b2b.taxi.tst.yandex.net"
            GEOFIX_HOST = "api.delivery-sandbox.com"
            ROUTE = "/b2b/cargo/integration/v2/"
            ROUTE_V1 = "/b2b/cargo/integration/v1/"

        class LogPlatform:
            HOST = "b2b-authproxy.taxi.yandex.net"
            HOST_TEST = "b2b.taxi.tst.yandex.net"
            GEOFIX_HOST = "api.delivery-sandbox.com"
            # HOST = "api.delivery-sandbox.com"
            ROUTE = "/api/b2b/platform/"

        class ReversedSettings:
            REVERSED_POINT = [32.029979, 34.797653]  # [latitude, longitude] for reorder_reversed action

        def get_random_point():
            geojson = {"type": "Feature",
                       "properties": {"name": "Moscow", "cartodb_id": 42, "created_at": "2013-12-04T04:23:51+0100",
                                      "updated_at": "2013-12-04T04:32:35+0100", "name_latin": "Moscow"},
                       "geometry": {"type": "MultiPolygon",
                                    "coordinates": [[[[37.045003, 55.142201], [37.01989, 55.16112],
                                                      [37.015248, 55.183382],
                                                      [36.982938, 55.180355],
                                                      [36.961636, 55.208977],
                                                      [36.947708, 55.218168],
                                                      [36.950132, 55.238262],
                                                      [36.93724, 55.241391],
                                                      [36.952517, 55.264835],
                                                      [36.983412, 55.268138],
                                                      [36.990038, 55.276139],
                                                      [37.026036, 55.283021],
                                                      [36.983812, 55.296971],
                                                      [36.986441, 55.315589],
                                                      [36.94473, 55.329369],
                                                      [36.936134, 55.341257],
                                                      [36.856056, 55.380332],
                                                      [36.848266, 55.392082],
                                                      [36.861874, 55.401035],
                                                      [36.834296, 55.413987],
                                                      [36.803101, 55.440833],
                                                      [36.804512, 55.465508],
                                                      [36.815208, 55.465972],
                                                      [36.816053, 55.508359],
                                                      [36.919474, 55.505845],
                                                      [36.919754, 55.515446],
                                                      [36.93967, 55.513477],
                                                      [36.935058, 55.496155],
                                                      [36.977651, 55.493772],
                                                      [36.973446, 55.45546],
                                                      [36.994017, 55.458318],
                                                      [37.019234, 55.445129],
                                                      [37.020071, 55.456786],
                                                      [37.036818, 55.464061],
                                                      [37.060613, 55.46266],
                                                      [37.089283, 55.441232],
                                                      [37.110774, 55.448399],
                                                      [37.117006, 55.438057],
                                                      [37.1418, 55.443081], [37.095406, 55.463119],
                                                      [37.093361, 55.470404],
                                                      [37.139813, 55.473409],
                                                      [37.125616, 55.497223],
                                                      [37.136931, 55.513136],
                                                      [37.118631, 55.513137],
                                                      [37.115906, 55.529998],
                                                      [37.12547, 55.549963],
                                                      [37.087353, 55.590355],
                                                      [37.116462, 55.605636],
                                                      [37.123927, 55.598922],
                                                      [37.146117, 55.60938],
                                                      [37.172023, 55.605184],
                                                      [37.185474, 55.618785],
                                                      [37.227259, 55.620061],
                                                      [37.240713, 55.643688],
                                                      [37.271434, 55.651479],
                                                      [37.305682, 55.646307],
                                                      [37.322908, 55.650889],
                                                      [37.319522, 55.664281],
                                                      [37.358452, 55.662576],
                                                      [37.369999, 55.667997],
                                                      [37.393928, 55.660883],
                                                      [37.415457, 55.664765],
                                                      [37.404032, 55.671043],
                                                      [37.417481, 55.680776],
                                                      [37.386661, 55.711147],
                                                      [37.368948, 55.745982],
                                                      [37.370601, 55.788192],
                                                      [37.344497, 55.768598],
                                                      [37.332302, 55.771934],
                                                      [37.348733, 55.796382],
                                                      [37.374481, 55.792363],
                                                      [37.393919, 55.829862],
                                                      [37.362157, 55.822037],
                                                      [37.333004, 55.845285],
                                                      [37.342022, 55.860207],
                                                      [37.377591, 55.868329],
                                                      [37.376182, 55.854507],
                                                      [37.394423, 55.854571],
                                                      [37.411159, 55.871002],
                                                      [37.372702, 55.881694],
                                                      [37.365754, 55.914104],
                                                      [37.377823, 55.921114],
                                                      [37.356463, 55.929954],
                                                      [37.343707, 55.924183], [37.33132, 55.93387],
                                                      [37.354099, 55.938907],
                                                      [37.335026, 55.953589],
                                                      [37.371972, 55.956138],
                                                      [37.394025, 55.948647],
                                                      [37.413904, 55.954532],
                                                      [37.408413, 55.924135],
                                                      [37.389973, 55.903831],
                                                      [37.40942, 55.880688],
                                                      [37.485935, 55.888399],
                                                      [37.537191, 55.907591],
                                                      [37.519479, 55.941763],
                                                      [37.543175, 55.943897],
                                                      [37.537429, 55.952877],
                                                      [37.563216, 55.951335],
                                                      [37.55595, 55.909555],
                                                      [37.578601, 55.911434],
                                                      [37.637352, 55.898608],
                                                      [37.703052, 55.893412],
                                                      [37.830081, 55.829153],
                                                      [37.837369, 55.82249],
                                                      [37.843401, 55.774735],
                                                      [37.842655, 55.746734],
                                                      [37.882541, 55.74934],
                                                      [37.890085, 55.741604],
                                                      [37.864238, 55.734717],
                                                      [37.876396, 55.720437],
                                                      [37.923585, 55.731225],
                                                      [37.967428, 55.716249],
                                                      [37.944604, 55.697207],
                                                      [37.960204, 55.692774],
                                                      [37.963378, 55.673656],
                                                      [37.920472, 55.676143],
                                                      [37.913291, 55.683317],
                                                      [37.928568, 55.695127],
                                                      [37.905442, 55.706993],
                                                      [37.886971, 55.705215],
                                                      [37.856728, 55.675683],
                                                      [37.832464, 55.683038],
                                                      [37.840962, 55.655559],
                                                      [37.795848, 55.624226],
                                                      [37.753831, 55.601597],
                                                      [37.684567, 55.574055],
                                                      [37.666359, 55.571517],
                                                      [37.60032, 55.575374],
                                                      [37.589454, 55.557683],
                                                      [37.578504, 55.521679],
                                                      [37.608096, 55.509844],
                                                      [37.611354, 55.489635],
                                                      [37.565485, 55.487418],
                                                      [37.560845, 55.473387],
                                                      [37.54475, 55.472646], [37.54592, 55.459718],
                                                      [37.532764, 55.453685],
                                                      [37.538293, 55.43757],
                                                      [37.5026, 55.438014], [37.484551, 55.458003],
                                                      [37.457993, 55.465437],
                                                      [37.445218, 55.481899],
                                                      [37.411257, 55.462932],
                                                      [37.394573, 55.469007],
                                                      [37.374121, 55.445515],
                                                      [37.400983, 55.44449],
                                                      [37.387338, 55.434646],
                                                      [37.427369, 55.432866],
                                                      [37.437352, 55.415383],
                                                      [37.467019, 55.41344],
                                                      [37.471193, 55.390449],
                                                      [37.462693, 55.367786],
                                                      [37.454663, 55.380059],
                                                      [37.427315, 55.364443],
                                                      [37.443347, 55.352592],
                                                      [37.420927, 55.350844],
                                                      [37.406942, 55.336124],
                                                      [37.429062, 55.314933],
                                                      [37.409951, 55.309164],
                                                      [37.384066, 55.316204],
                                                      [37.415868, 55.290256],
                                                      [37.405315, 55.250576],
                                                      [37.351865, 55.238635],
                                                      [37.333392, 55.228672],
                                                      [37.300847, 55.224526],
                                                      [37.306992, 55.240122],
                                                      [37.271561, 55.258824],
                                                      [37.269605, 55.240722],
                                                      [37.245516, 55.239265],
                                                      [37.219005, 55.253109],
                                                      [37.19394, 55.23481], [37.163361, 55.231579],
                                                      [37.169879, 55.164339],
                                                      [37.140776, 55.164378],
                                                      [37.14208, 55.155676], [37.11121, 55.149187],
                                                      [37.064393, 55.147119],
                                                      [37.045003, 55.142201]]], [
                                                        [[37.845327, 55.813562],
                                                         [37.872252, 55.822498],
                                                         [37.884128, 55.816661],
                                                         [37.865743, 55.804208],
                                                         [37.845327, 55.813562]]], [
                                                        [[37.131602, 56.016446],
                                                         [37.16173, 56.013221],
                                                         [37.188978, 56.021224],
                                                         [37.260562, 55.993143],
                                                         [37.261109, 55.968067],
                                                         [37.242027, 55.979274],
                                                         [37.218912, 55.98036],
                                                         [37.205811, 55.963213],
                                                         [37.217713, 55.948026],
                                                         [37.18251, 55.958733],
                                                         [37.146611, 55.963719],
                                                         [37.144393, 55.989316],
                                                         [37.151171, 55.999549],
                                                         [37.131602, 56.016446]]]]}}
            # Get a random polygon from the geojson
            polygon = random.choice(geojson['geometry']['coordinates'])

            # Get a random point inside the polygon
            min_lon, min_lat, max_lon, max_lat = get_bounds(polygon)
            while True:
                point = [random.uniform(min_lon, max_lon), random.uniform(min_lat, max_lat)]
                if is_point_inside_polygon(point, polygon):
                    return point

        def get_bounds(polygon):
            # Calculate the bounding box of the polygon
            min_lon, min_lat = float('inf'), float('inf')
            max_lon, max_lat = float('-inf'), float('-inf')
            for ring in polygon:
                for point in ring:
                    lon, lat = point
                    min_lon = min(min_lon, lon)
                    min_lat = min(min_lat, lat)
                    max_lon = max(max_lon, lon)
                    max_lat = max(max_lat, lat)
            return min_lon, min_lat, max_lon, max_lat

        def is_point_inside_polygon(point, polygon):
            # Check if a point is inside a polygon using the ray casting algorithm
            x, y = point
            inside = False
            for ring in polygon:
                i, j = len(ring) - 1, 0
                for k in range(len(ring)):
                    xi, yi = ring[i]
                    xj, yj = ring[j]
                    if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                        inside = not inside
                    i, j = j, k
            return inside

        class ReportSettings:
            FOR_TODAY = True  # automatically generates report for today
            TIME_ZONES = {
                "Russia": 3,
                "Turkey": 3,
                "Israel": 3,
                "Serbia": 2,
                "Mexico": -6
            }

        class SortingFile:
            MANUAL_CUTOFF = False
            STATUSES = Statuses.ROUTED

        class Products:
            EXPRESS = "Express"
            LOG_PLATFORM = "LogPlatform"
            UNITED = "UnitedAPI"

        class Client:
            def __init__(self, name, token):
                self.name = name
                self.token = token

        class Settings:
            TRACE = False
            TEST = False
            JSON = False
            PRODUCT = Products.EXPRESS
            USE_GEOFIX = False  # will switch all requests to api.delivery-sandbox.com
            COUNTRY: Optional[str] = "Israel"  # for GeoFix purposes, optional
            CITY: Optional[str] = "Tel-Aviv"  # for GeoFix purposes, optional
            CITY_COORDINATES: Optional[str] = [32.086827, 34.789577]  # [latitude, longitude], for GeoFix purposes
            CLIENT: Client = None

        @retry(retry=retry_if_exception_type(IOError))
        def get_client() -> (str, str):
            """
            Requests a client and finds it in "token.json" file
            :return (client_name, token)
            """
            try:
                clients = json.loads(open("token.json", "r", encoding="utf-8").read())['clients']
            except (FileNotFoundError, FileExistsError, json.JSONDecodeError, KeyError):
                clients = {}

            input_client = input(
                f"{Fore.LIGHTWHITE_EX}[{Settings.PRODUCT}] {Fore.LIGHTMAGENTA_EX}Please enter clients' name or token.{Fore.BLUE} To switch to other API input LogAPI, Express or United{Fore.RESET}{Fore.RESET}{Fore.LIGHTMAGENTA_EX}: ")

            if input_client.lower() == "logapi":
                Settings.PRODUCT = Products.LOG_PLATFORM
                return get_client()

            if input_client.lower() == "express":
                Settings.PRODUCT = Products.EXPRESS
                return get_client()

            if input_client.lower() == "united":
                Settings.PRODUCT = Products.UNITED
                return get_client()

            clients_separated = input_client.split(", ")

            def iter_clients():
                for client_separated in clients_separated:
                    if len(client_separated) < 32:
                        try:
                            yield Client(client_separated, clients[client_separated.lower()])
                        except KeyError:
                            print(
                                f"{Fore.LIGHTRED_EX}Client {Fore.RESET}{Style.BRIGHT}{client_separated}{Fore.LIGHTRED_EX} was not found. {Fore.RESET}Please enter the token or try again\n")
                            raise IOError("client was not found")
                    else:
                        yield Client("client", client_separated)

            return [q for q in iter_clients()]

        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context

        init(autoreset=True)
        clients = get_client()
        host = Express.HOST if Settings.PRODUCT == Products.EXPRESS else LogPlatform.HOST

        http_client = http.client.HTTPSConnection(host)
        http_client_sandbox = http.client.HTTPSConnection(Express.GEOFIX_HOST)
        http_client_test = http.client.HTTPSConnection(Express.HOST_TEST)
        token = ""
        client = ""

        def get_headers(token, accept_language="en"):
            return {
                'Accept-Language': accept_language,
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

        async def make_request_async(u, m="POST", h=None, b=None, hst=host, t=""):
            async with httpx.AsyncClient() as c:
                if b is None:
                    b = {}

                route = Express.ROUTE if Settings.PRODUCT == Products.EXPRESS else LogPlatform.ROUTE
                if 'https' not in u:
                    hst = LogPlatform.HOST if Settings.PRODUCT == Products.LOG_PLATFORM else Express.HOST
                    hst = Express.GEOFIX_HOST if Settings.USE_GEOFIX else hst
                    u = f"https://{hst}{route}{u}"

                h = get_headers(token if t == "" else t)

                if Settings.JSON:
                    print(Fore.LIGHTYELLOW_EX + m, u)
                    print(Fore.RED + "Headers:\n" + json.dumps(h, indent=4))
                    print(Fore.YELLOW + "Payload:\n" + json.dumps(b, indent=4))

                try:
                    r = await c.post(u, json=b, headers=h) if m == "POST" else await c.get(u, headers=h)
                except ValueError:
                    await asyncio.sleep(0.1)
                    r = await c.post(u, json=b, headers=h) if m == "POST" else await c.get(u, headers=h)
                    traceback.print_exc()

                try:
                    if Settings.JSON:
                        print(Fore.GREEN + "Response:\n" + json.dumps(r.json(), indent=4) + "\n")
                    return r.json()
                except json.decoder.JSONDecodeError:
                    return {}

        def make_request(endpoint, payload, method="POST", claim="", different_token=False):
            different_token = Settings.CLIENT.token if not different_token else different_token

            headers = {
                'Accept-Language': 'en',
                'Authorization': f'Bearer {different_token}',
                'Content-Type': 'application/json'
            }

            route = Express.ROUTE if Settings.PRODUCT == Products.EXPRESS else LogPlatform.ROUTE
            try:
                tc = http_client_sandbox if Settings.USE_GEOFIX else http_client
                tc = http_client_test if Settings.TEST else tc

                tc.request(method, f"{route}{endpoint}", json.dumps(payload) if method == "POST" else None, headers)

                http_response = tc.getresponse()
                if Settings.TRACE:
                    print(
                        f"\n{Fore.LIGHTBLUE_EX}TraceID {route + endpoint}: " + http_response.headers.get("X-YaTraceId",
                                                                                                         "No TraceID"))
                http_response = http_response.read()
                if Settings.JSON:
                    print(Fore.LIGHTYELLOW_EX + method, route + endpoint)
                    print(Fore.RED + "Headers:\n" + json.dumps(headers, indent=4))
                    print(Fore.YELLOW + "Payload:\n" + json.dumps(payload, indent=4))
                    print(Fore.GREEN + "Response:\n" + json.dumps(json.loads(http_response), indent=4) + "\n")
                try:
                    return json.loads(http_response) | {"claim_id": claim}
                except json.decoder.JSONDecodeError:
                    return {"response": http_response}
            except socket.gaierror:
                print(f"{Fore.LIGHTRED_EX}No internet connection")
                exit(1)

        def bulk_request(m: list[dict], c: list[str]):
            yield (make_request(claiming(method.get('method'), claim), method.get('payload'), claim=claim) for method in
                   m
                   for
                   claim in c)

        def claiming(source, predicate, lookup="{claim_id}"):
            return source.replace(lookup, predicate)

        def handle_response(r: dict, f, check_claim=False):
            try:
                if check_claim:
                    assert check_claim and 'claim_id' in r.keys(), f"{Fore.LIGHTRED_EX}No claim_id is specified{Fore.RESET}"
                    assert r['claim_id'] != "", f"{Fore.LIGHTRED_EX}No claim_id is specified{Fore.RESET}"
                try:
                    print(
                        f"{Fore.LIGHTRED_EX}{r['claim_id']} - {r['message']}{Fore.RESET}" if 'code' in r.keys() else f"{Fore.LIGHTGREEN_EX}{f(r)}{Fore.RESET}")
                except KeyError:
                    print(f"{r['claim_id']} - {Fore.LIGHTRED_EX}{r}{Fore.RESET}")
            except AssertionError as e:
                print(e)

        def find_input():
            if Settings.PRODUCT == Products.EXPRESS:
                statuses = [a.replace(" ", "") for a in input(
                    f"Enter statuses to search separated by comma {Fore.LIGHTBLUE_EX}(performer_draft, pickuped){Fore.RESET} or leave it empty: ").split(
                    ", ")]
                interval = input(
                    f"Enter the pickup interval to find claims for {Fore.LIGHTBLUE_EX}(12:00, 12:00+00:00, 2022-12-14T10:00:00+00:00){Fore.RESET} or leave it empty: ")
                pickup = input(
                    f"Enter the pickup location to find claims for. {Fore.LIGHTBLUE_EX}Copy it from adminka, it should match! {Fore.RESET}")

                statuses = list(filter(lambda x: x in Statuses.all_statuses(), statuses))

                temp = interval.split("+")
                if "+" in interval and "-" not in interval:
                    interval = f"{datetime.datetime.now().strftime('%Y-%m-%d')}T{temp[0]}:00+{temp[1]}"
                elif ":" in interval and "-" not in interval:
                    interval = f"{datetime.datetime.now().strftime('%Y-%m-%d')}T{temp[0]}:00+00:00"
                else:
                    interval = temp[0]

            elif Settings.PRODUCT == Products.LOG_PLATFORM:
                statuses = [a.replace(" ", "") for a in input(
                    f"Enter statuses to search separated by comma {Fore.LIGHTBLUE_EX}(DELIVERY_DELIVERED, FINISHED){Fore.RESET} or leave it empty: ").split(
                    ", ")]
                interval = [input(
                    f"Enter the start creation time to find claims for {Fore.LIGHTBLUE_EX}(2022-12-14T10:00:00+00:00, 2022-12-14){Fore.RESET} or leave it empty: "),
                    input(
                        f"Enter the end creation time to find claims for {Fore.LIGHTBLUE_EX}(2022-12-15T10:00:00+00:00, 2022-12-15){Fore.RESET} or leave it empty: ")]
                pickup = input(
                    f"Enter the pickup station to find claims for or leave it empty. {Fore.LIGHTBLUE_EX}Copy it from adminka, it should match! {Fore.RESET}")

                if interval[0] == "":
                    interval[0] = "2022-01-01"

                if interval[1] == "":
                    interval[1] = datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(hours=24),
                                                             "%Y-%m-%d")

                for i in range(2):
                    if "T" not in interval[i]:
                        interval[i] = f"{interval[i]}T00:00:00+00:00"

                # statuses = list(filter(lambda x: x in Statuses.all_statuses(), statuses))

            return [interval, pickup, statuses]

        def log(text, end=False):
            ending = '\n' if end else '\r'
            print(text + " " * 30, end=ending)

        def logapi_requests_info(start, end, statuses):
            response = make_request("requests/info", {
                "from": start,
                "to": end
            })

            if "error_details" in response.keys():
                print(
                    f"Making request for claims {Fore.CYAN}from {start.split('T')[0]} to {end.split('T')[0]}{Fore.RESET} - {Fore.LIGHTRED_EX}Too many claims requested{Fore.RESET}")

                start = datetime.datetime.fromisoformat(start)
                end = datetime.datetime.fromisoformat(end)
                middle = start + (end - start) / 2

                middle, start, end = middle.isoformat(), start.isoformat(), end.isoformat()

                start_1, end_2 = start, end
                end_1, start_2 = middle, middle
                return logapi_requests_info(start_1, end_1, statuses) + logapi_requests_info(start_2, end_2, statuses)
            else:
                print(
                    f"Making request for claims {Fore.CYAN}from {start.split('T')[0]} to {end.split('T')[0]}{Fore.RESET} - {Fore.LIGHTGREEN_EX}{len(response['requests'])} requests found{Fore.RESET}")
                time.sleep(0.2)

                claims = []
                for r in response['requests']:
                    if r['state']['status'] in statuses or '' in statuses:
                        # print(f"{r['request_id']} - {r['request']['destination']['custom_location']['latitude']}, {r['request']['destination']['custom_location']['longitude']}: {r['request']['info']['comment'].split('Turkey, ')[1:2] or 'No Address'}")
                        claims.append(r['request_id'])
                return claims

        def find_claim(claim):
            claim_id = ""
            try:
                response = make_request("claims/search", {"external_order_id": claim, "limit": 5, "offset": 0})[
                    'claims']
                for claim_response in response:
                    if len(claim_response['route_points']) <= 3:
                        claim_id = claim_response['id']
            except (KeyError, IndexError):
                pass

            return claim_id

        def int_input(prompt):
            while True:
                try:
                    temp = int(input(prompt))
                    return temp
                except ValueError:
                    continue
            return 0

        def radio_input(prompt, ops):
            while True:
                try:
                    temp = input(prompt)
                    if temp not in ops:
                        raise ValueError
                    return temp
                except ValueError:
                    continue
            return 0

        def get_create_data(pickup_coordinates, pickup_address, coordinates, address, final_status, sdd=True):
            items = [
                {
                    "cost_currency": "RUB",
                    "cost_value": "0.00",
                    "droppof_point": 2,
                    "pickup_point": 1,
                    "quantity": 1,
                    "size": {
                        "height": 0,
                        "length": 0,
                        "width": 0
                    },
                    "title": "Item",
                    "weight": 1
                }
            ]

            source = {"coordinates": list(pickup_coordinates)} if pickup_coordinates else {}
            source["fullname"] = pickup_address if pickup_address else f"Untitled point: {pickup_coordinates}"

            destination = {"coordinates": list(coordinates)} if coordinates else {}
            destination["fullname"] = address if address else f"Untitled point: {coordinates}"

            route_points = [
                {
                    "address": source,
                    "contact": {
                        "name": "Test",
                        "phone": "+79999999999"
                    },
                    "external_order_id": "test_order",
                    "point_id": 1,
                    "skip_confirmation": True,
                    "type": "source",
                    "visit_order": 1
                },
                {
                    "address": destination,
                    "contact": {
                        "name": "Test",
                        "phone": "+79999999999"
                    },
                    "external_order_id": "test_order",
                    "point_id": 2,
                    "skip_confirmation": True,
                    "type": "destination",
                    "visit_order": 2
                }
            ]

            result = {
                "items": items,
                "route_points": route_points,
                "comment": f"cargostatus:{final_status}",
                "optional_return": False,
                "referral_source": "",
                "skip_act": True,
                "skip_client_notify": True,
                "skip_door_to_door": False,
                "skip_emergency_notify": True
            }

            if sdd and pickup_coordinates:
                delivery_methods = make_request("delivery-methods", {"start_point": pickup_coordinates})
                if delivery_methods.get('same_day_delivery', {}).get('available_intervals'):
                    interval = delivery_methods['same_day_delivery']['available_intervals'][0]
                    result['same_day_data'] = {"delivery_interval": interval}
                else:
                    print(f"{Fore.LIGHTRED_EX}No available intervals for this client{Fore.RESET}")
                    return {}

            return result

        async def claims_cancel(claim):
            async with semaphore:
                methods = [
                    {
                        "method": "claims/cancel?claim_id={claim_id}",
                        "payload": {"cancel_state": "free", "version": 1}
                    },
                    {
                        "method": "claims/cancel?claim_id={claim_id}",
                        "payload": {"cancel_state": "paid", "version": 1}
                    }
                ]
                if len(claim) != 32:
                    claim_id = find_claim(claim)
                    claim = claim if claim_id == '' else claim_id
                tries = 0
                for method in methods:
                    try:
                        action_response = await make_request_async(method['method'].replace("{claim_id}", claim), "POST",
                                                       b=method['payload'])
                        action_response['claim_id'] = claim
                    except http.client.RemoteDisconnected:
                        continue
                    tries += 1
                    if tries > 1 or 'status' in action_response.keys():
                        tries = 0
                        f = lambda j: f"{j['claim_id']} - {j['status']}"
                        handle_response(action_response, f, check_claim=True)
                    if 'status' in action_response.keys():
                        return


        async def lp_reorder(c, td):
            # THIS FUNCTIONALITY IS DELETED DUE ERRORS ON THE LOGPLATFORM SIDE
            # r = make_request(f"request/info?request_id={c}", {}, method="GET")
            # if 'request' not in r.keys():
            #     print(f"{Fore.LIGHTRED_EX}{c} - not found {r}{Fore.RESET}")
            #     continue
            #
            # r['request']['info']['operator_request_id'] += "_" + str(random.randint(10000, 99999))
            # del r['request']['destination']['interval']
            # del r['request']['destination']['interval_utc']
            # del r['request']['destination']['custom_location']['details']
            #
            # body = r['request']

            async with semaphore:
                try:
                    r = await make_request_async(f"https://api.delivery-sandbox.com/request/{c}", "GET")
                    r[0]['body']['info']['operator_request_id'] += "_" + str(random.randint(10000, 99999))
                except (IndexError, KeyError):
                    print(f"{Fore.LIGHTRED_EX}{c}{Fore.RED} - not found{Fore.RESET}")
                    return []

                body = r[0]['body']
                offers = await make_request_async("/offers/create", b=body)
                if 'offers' in offers.keys():
                    if len(offers['offers']) > 0:
                        reque = await make_request_async("/offers/confirm",
                                                         b={"offer_id": offers['offers'][0]['offer_id']})
                        if 'request_id' in reque.keys():
                            created_claims.append(reque['request_id'])
                            print(f"{Fore.LIGHTGREEN_EX}{c} → {reque['request_id']}{Fore.RESET}")

                            url = f"https://api.delivery-sandbox.com/change_request_id?old_request_id={c}&new_request_id={reque['request_id']}"
                            await make_request_async(url, "GET")
                        else:
                            print(f"{Fore.LIGHTRED_EX}{c} - error: {reque}{Fore.RESET}")
                else:
                    print(f"{Fore.LIGHTRED_EX}{c} - error: {offers}{Fore.RESET}")

                td.claims.extend(created_claims)

        def format_timezone_offset(offset):
            sign = '+' if offset >= 0 else '-'
            offset_hours = abs(offset)
            return f"{sign}{offset_hours:02d}:00"

        def find(interval="", pickup="", statuses=[], end_date="", date="", time_zone=0, duplicates=False,
                 sorting=False,
                 action="", final_client=True):
            date_split = date.split(" - ")

            global raw_data
            global raw_data_express

            if len(date_split) > 1:
                report_start, report_end = date_split
            else:
                report_start, report_end = date_split[0], date_split[0]

            constraints = {}
            if action == "report":
                constraints = {
                    "created_from": f"{report_start}T00:00:00{format_timezone_offset(time_zone)}",
                    "created_to": f"{report_end}T00:00:00{format_timezone_offset(time_zone)}"
                }

            if Settings.PRODUCT == Products.EXPRESS:
                if len(statuses) == 0:
                    statuses = ['']

                claims = []
                external_order_ids = []
                dups = []
                routes = [["barcode", "route_id"]]
                search = "/claims/search"
                for status in statuses:
                    status_dict = {"status": status} if status != '' else {}
                    results = make_request(search, {
                        "limit": 500,
                        "offset": 0,
                    } | status_dict | constraints)
                    while True:
                        any_result = False
                        if 'claims' not in results.keys():
                            break
                        for result in results['claims']:
                            if interval != '':
                                if 'same_day_data' not in result.keys():
                                    continue
                                if interval not in result['same_day_data']['delivery_interval']['from']:
                                    continue
                            if pickup != '':
                                if result['route_points'][0]['address']['fullname'] != pickup:
                                    continue
                            if end_date != '':
                                created = time.mktime(
                                    datetime.datetime.strptime(result['created_ts'].split("T")[0],
                                                               "%Y-%m-%d").timetuple())
                                end = time.mktime(datetime.datetime.strptime(end_date, "%Y-%m-%d").timetuple())
                                if created < end:
                                    continue
                            if date != '':
                                date_new = time.mktime(datetime.datetime.strptime(report_start, "%Y-%m-%d").timetuple())
                                date_new_end = time.mktime(
                                    datetime.datetime.strptime(report_end, "%Y-%m-%d").timetuple())
                                start_ts = date_new + time_zone * 3600
                                end_ts = date_new_end + time_zone * 3600 + 24 * 3600
                                updated = time.mktime(datetime.datetime.strptime(result['created_ts'].split(".")[0],
                                                                                 "%Y-%m-%dT%H:%M:%S").timetuple())

                                if not (start_ts <= updated <= end_ts):
                                    continue
                                # else:
                                #     print(result['updated_ts'], result['status'])
                            any_result = True
                            if not duplicates:
                                print(Fore.LIGHTGREEN_EX + result['id'] + Fore.RESET)
                            claims.append(result['id'])
                            pickup_point = result['route_points'][0]

                            if action == "report":
                                claim = result
                                sheet_updated = claim['updated_ts'].split(".")[0]
                                sheet_pickup = claim['same_day_data']['delivery_interval'][
                                    'from'].split(".")[0] if 'same_day_data' in claim.keys() else ""

                                zone = (
                                           "-" if time_zone < 0 else "+") + f"{'-' if time_zone < 0 else ''}0{abs(time_zone)}:00"

                                currency = "RSD"
                                cash_amount = "0"
                                if 'comment' in claim:
                                    try:
                                        cash_amount = claim['route_points'][1]['address']['comment'].split(
                                            currency)
                                        if len(cash_amount) <= 1:
                                            cash_amount = claim['comment'].split(currency)
                                        if len(cash_amount) > 1:
                                            cash_amount = \
                                                cash_amount[0].replace(":", "").split("otkup ")[1].split(
                                                    f" {currency}")[
                                                    0].replace(
                                                    " ", "")
                                        else:
                                            cash_amount = "0"
                                    except (IndexError, KeyError):
                                        cash_amount = "0"

                                sheet_updated = (datetime.datetime.fromisoformat(
                                    sheet_updated) + datetime.timedelta(
                                    hours=time_zone)).astimezone().replace(
                                    microsecond=0).isoformat().replace("+00:00", zone)
                                if sheet_pickup != "":
                                    sheet_pickup = (datetime.datetime.fromisoformat(
                                        sheet_pickup) + datetime.timedelta(
                                        hours=time_zone)).astimezone().replace(
                                        microsecond=0).isoformat().replace("+00:00", zone)

                                claim_id = claim['id']

                                d = [client, claim_id, claim['route_points'][1][
                                    'external_order_id'] if 'external_order_id' in
                                                            claim['route_points'][
                                                                1].keys() else '',
                                     claim['route_points'][0]['address']['fullname'],
                                     claim['route_points'][1]['address']['fullname'], claim['status'],
                                     sheet_updated.split("T")[0],
                                     sheet_updated.split("T")[1].split(".")[0].split("+")[0],
                                     cash_amount,
                                     claim['performer_info'][
                                         'legal_name'] if 'performer_info' in claim.keys() else '',
                                     claim['performer_info'][
                                         'courier_name'] if 'performer_info' in claim.keys() else '',
                                     claim['route_points'][1]['contact'][
                                         'name'] if 'performer_info' in claim.keys() else '',
                                     ", ".join(claim['route_points'][1]['return_reasons']) if ((claim[
                                                                                                    'status'] in [
                                                                                                    'returned_finish',
                                                                                                    'returning']) and (
                                                                                                       'return_reasons' in
                                                                                                       claim[
                                                                                                           'route_points'][
                                                                                                           1].keys())) else '',
                                     claim["route_id"] if 'route_id' in claim.keys() else "",
                                     sheet_pickup]
                                if 'same_day_data' in claim.keys():
                                    raw_data.append(d)
                                else:
                                    raw_data_express.append(d)

                            if duplicates:
                                if 'external_order_id' in pickup_point.keys():
                                    if pickup_point['external_order_id'] in external_order_ids:
                                        dups.append(pickup_point['external_order_id'])
                                        print(Fore.LIGHTGREEN_EX + pickup_point['external_order_id'] + Fore.RESET)

                                    external_order_ids.append(pickup_point['external_order_id'])
                                    external_order_ids = list(set(external_order_ids))

                            if sorting:
                                if 'route_id' in result.keys():
                                    routes.append([pickup_point['external_order_id'], result['route_id']])

                        # if len(results['claims']) == 0:
                        #     print(f"{Fore.LIGHTYELLOW_EX}The search was completed{Fore.RESET}")
                        if not any_result:
                            break
                        if 'cursor' not in results.keys():
                            break
                        cursor = results['cursor']
                        results = make_request(search, {
                            "cursor": cursor
                        })

                    if sorting:
                        print("Generating the sorting_couriers file")
                if len(claims) == 0:
                    print(Fore.LIGHTRED_EX + "No claims were found" + Fore.RESET)

                if action == "report":
                    if final_client:
                        columns = ["client", "claim_id", "order_id", "pickup_location", "address", "status",
                                   "date", "time",
                                   "amount",
                                   "park_name", "courier_name",
                                   "recipient_name", "return_reasons", "route_id", "pickup_time"]

                        df = pd.DataFrame(raw_data, columns=columns)
                        df_express = pd.DataFrame(raw_data_express, columns=columns)

                        file_name = f"{'&'.join([cl.name for cl in (clients if len(clients) < 5 else [Client(name='clients', token='token')])])}_report-{date}.xlsx"
                        print(f"{Fore.LIGHTGREEN_EX}Saving report in current directory with the name {file_name}")
                        writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
                        df.to_excel(writer, sheet_name=f'Same-Day', index=False)
                        df_express.to_excel(writer, sheet_name=f'Express', index=False)
                        writer.close()
            elif Settings.PRODUCT == Products.LOG_PLATFORM:
                claims = logapi_requests_info(report_start, report_end, statuses)

            print(f"{Fore.LIGHTYELLOW_EX}There are {len(claims)} claims found in total")

            return claims

        claims = []
        command = ""

        try:
            with open("claims", "r", encoding="utf-8") as f:
                claims = f.read().split("\n")
                first_row = claims[0]
        except (FileExistsError, FileNotFoundError):
            pass

        if command != 'create':
            claims = list(set(claims))

        while command != "exit":
            commands = input(
                f"\n{Fore.LIGHTWHITE_EX}[{Settings.PRODUCT}]{Fore.RESET}{Fore.LIGHTYELLOW_EX} Enter an action: {Fore.RESET}").split()

            try:
                options = commands[1:]
                command = commands[0]
            except IndexError:
                continue

            if '-logapi' in options:
                Settings.PRODUCT = Products.LOG_PLATFORM

            if '-express' in options:
                Settings.PRODUCT = Products.EXPRESS

            Settings.USE_GEOFIX = '-sandbox' in options
            Settings.TRACE = '-trace' in options
            Settings.JSON = '-json' in options
            Settings.TEST = '-test' in options

            todo_claims = {}
            original_claims = deepcopy(claims)

            which_client = 0

            for client_instance in clients:

                if client != '' and claims != original_claims:
                    todo_claims[client] = claims

                Settings.CLIENT = client_instance
                client = client_instance.name
                token = client_instance.token

                if isinstance(original_claims, dict):
                    claims = original_claims.get(client, [])

                # LET'S GET SOME DATA
                if which_client < 1:
                    match command:
                        case Actions.CREATE:
                            if Settings.PRODUCT == "Express":
                                create_type = radio_input(
                                    Fore.LIGHTWHITE_EX + "Choose the of generation: " + Fore.LIGHTMAGENTA_EX + "(random, file_address, file_coordinates): " + Fore.RESET,
                                    ["random", "file_address", "file_coordinates"])
                                claims_count = int_input(
                                    Fore.LIGHTWHITE_EX + "Please enter the amount of orders to be created: ") if create_type == "random" else 0
                                claims_type = radio_input(
                                    Fore.LIGHTWHITE_EX + "Choose the best generate type which suits your needs: " + Fore.LIGHTMAGENTA_EX + "(o2m, m2o, m2m): " + Fore.RESET,
                                    ["o2m", "m2o", "m2m"]) if create_type == "random" else "m2m"
                                final_status = radio_input(
                                    Fore.LIGHTWHITE_EX + "Choose the final status you want to get or leave it empty: " + Fore.LIGHTMAGENTA_EX + "(delivered_finish, returned_finish, performer_not_found, cancelled_by_taxi): " + Fore.RESET,
                                    ["delivered_finish", "returned_finish", "performer_not_found", "cancelled_by_taxi",
                                     ""])
                                print()
                                pickup = input(
                                    Fore.LIGHTCYAN_EX + "Please input the pickup address in string or like this: lat, lng or leave it empty to inherit from the first row in the file: ")


                            elif Settings.PRODUCT == "LogAPI":
                                print(Fore.RED + "This feature is currently unsupported by the script in LogAPI")
                                continue
                        case Actions.REPORT:
                            raw_data = []
                            raw_data_express = []
                            country = Settings.COUNTRY

                            input_country = input(
                                f"Using {Fore.LIGHTBLUE_EX}{country}{Fore.RESET} as your country. If it's not ok, specify the country here: ")
                            country = country if input_country not in ReportSettings.TIME_ZONES.keys() else input_country

                            time_zone = ReportSettings.TIME_ZONES[country]

                            try:
                                time_zone_str = f"+{time_zone}" if time_zone > 0 else str(time_zone)
                                time_zone = int(input(
                                    f"Using {Fore.LIGHTBLUE_EX}GMT{time_zone_str}{Fore.RESET} as your time zone. If it's not ok, specify the time zone here: "))
                            except ValueError:
                                input_time_zone = time_zone

                            date = datetime.datetime.now().strftime('%Y-%m-%d')
                            date_input = input(
                                f"We'll upload report for {Fore.LIGHTBLUE_EX}{date}{Fore.RESET}. Is it ok? If not, specify the date in this format or date range like {Fore.LIGHTBLUE_EX}2022-12-01 - 2022-12-31{Fore.RESET}: ")
                            date = date_input if date_input != "" else date
                            print("")

                            interval, pickup, statuses = find_input()
                            if len(statuses) == 0:
                                statuses = []

                        case Actions.FIND:
                            interval, pickup, statuses = find_input()

                        case Actions.DUPLICATES:
                            print(f"Let's find some duplicates")
                            interval, pickup, statuses = find_input()
                            end_date = input(
                                f"Specify the end date until which we should locate duplicates like {Fore.LIGHTBLUE_EX}2022-12-31{Fore.RESET} or leave it empty: ")
                            if len(statuses) == 0:
                                statuses = Statuses.all_statuses()

                        case Actions.REORDER:
                            if Settings.PRODUCT == Products.EXPRESS:
                                sdd = input(
                                    f"Claims will be created as {Fore.LIGHTBLUE_EX}SDD{Fore.RESET}, press Enter to continue. If you want claims to be created as "
                                    f"Express, enter {Fore.LIGHTBLUE_EX}Express{Fore.RESET}: ") != "Express"

                        case Actions.REVERSED:
                            reversed_corp, route_scheme, different_A = "!", "!", "!"
                            clients_file = json.loads(open("token.json", "r", encoding="utf-8").read())['clients']
                            print(f"{Fore.LIGHTWHITE_EX}Let's make some reversals")
                            while True:
                                reversed_corp = input(
                                    f"Claims will be loaded on behalf of the {Fore.LIGHTCYAN_EX}client itself{Fore.RESET}. Press Enter to proceed or input client name: ")
                                if reversed_corp not in clients_file.keys() and reversed_corp != "":
                                    print(
                                        Fore.LIGHTRED_EX + f"There is no client {Fore.RESET}{reversed_corp}{Fore.LIGHTRED_EX} found")
                                else:
                                    break
                            print(f"{Fore.LIGHTMAGENTA_EX}A - B - C: imagine the basic order example")

                            while True:
                                route_scheme = input(
                                    f"The order will be created as {Fore.LIGHTCYAN_EX}C - B - A{Fore.RESET}. Press Enter to proceed or input the scheme in format {Fore.LIGHTBLUE_EX}X - Y - Z{Fore.RESET} to change the route: ")
                                if (all(c in route_scheme.replace("B", "A").replace("C", "A") for c in "A- ") and len(
                                        route_scheme.split(" - ")) == 3) or route_scheme == "":
                                    break
                                else:
                                    print(Fore.LIGHTRED_EX + "The string should be in format A - B - C")

                            while True:
                                different_A = input(
                                    f"Do you want to change {Fore.LIGHTCYAN_EX}point A coordinates{Fore.RESET}? Press Enter to keep or input the coordinates in format {Fore.LIGHTBLUE_EX}(57.34234234, 38.343434){Fore.RESET}: ")
                                if len(different_A.split(", ")) == 2 or different_A == "":
                                    break
                                else:
                                    print(Fore.LIGHTRED_EX + "The string should be in format 57.342342, 28.459214")

                                print("\n")

                        case Actions.SORTING_FILE:
                            interval, pickup, statuses = find_input()

                        case Actions.SCANNED:
                            continue

                which_client += 1
                if len(clients) > 1:
                    print(f"{Fore.LIGHTWHITE_EX}[{client}]{Fore.RESET} {Fore.LIGHTBLUE_EX}Doing {command}{Fore.RESET}")

                # NOW DO THE REAL ACTION
                match command:
                    case Actions.CREATE:
                        # create_type, claims_count, claims_type, final_status, pickup
                        created_claims = []

                        pickup_address, pickup_coordinates = "", []
                        start_index = 0
                        if pickup == "":
                            if create_type in ['file_address', 'file_coordinates']:
                                pickup = first_row
                                pickup_coordinates = list(map(float, pickup.split(", ")))
                                start_index = 1
                        else:
                            try:
                                pickup_coordinates = list(map(float, pickup.split(", ")))
                            except (ValueError, IndexError):
                                pickup_address = pickup
                        pickup_coordinates.reverse()

                        claims = list(claims)
                        for i in range(start_index, claims_count if create_type == "random" else len(claims)):
                            address, coordinates = "", []
                            if create_type == "random":
                                if claims_type in ["m2m", 'm2o']:
                                    pickup_coordinates = get_random_point()
                                if claims_type in ['m2m', 'o2m']:
                                    coordinates = get_random_point()
                                pass
                            elif create_type == "file_address":
                                address = claims[i]
                                pass
                            elif create_type == "file_coordinates":
                                coordinates = list(map(float, claims[i].split(', ')))
                                coordinates.reverse()

                            data = get_create_data(pickup_coordinates, pickup_address, coordinates, address,
                                                   final_status)
                            request_id = token_hex(16)
                            create_response = make_request(f"claims/create?request_id={request_id}", data)

                            if 'id' in create_response.keys():
                                created_claim = create_response['id']
                                created_claims.append(created_claim)

                            f = lambda j: f"{created_claim}"
                            handle_response(create_response, f)

                        claims = list(set(created_claims))
                        continue
                    case Actions.HELP:
                        attributes = inspect.getmembers(Actions, lambda a: not (inspect.isroutine(a)))
                        commands = [a[1] for a in attributes if not (a[0].startswith('__') and a[0].endswith('__'))]
                        print(
                            Fore.LIGHTWHITE_EX + "Here's the list of possible actions:" + Fore.LIGHTCYAN_EX + " \n– " + "\n– ".join(
                                commands))
                        continue

                    case Actions.FLUSH:
                        for claim in claims:
                            print(Fore.LIGHTGREEN_EX + claim + Fore.RESET)
                        print(
                            Fore.LIGHTYELLOW_EX + f"There are {Fore.LIGHTWHITE_EX}{len(claims)}{Fore.RESET}{Fore.LIGHTYELLOW_EX} claims in total for client {Fore.LIGHTWHITE_EX}{client}{Fore.RESET}")
                        continue

                    case Actions.COUNT:
                        print(
                            Fore.LIGHTYELLOW_EX + f"There are {Fore.LIGHTWHITE_EX}{len(claims)}{Fore.RESET}{Fore.LIGHTYELLOW_EX} claims in total for client {Fore.LIGHTWHITE_EX}{client}{Fore.RESET}")
                        continue

                    case Actions.ACCEPT:
                        methods = [
                            {
                                "method": "claims/accept?claim_id={claim_id}",
                                "payload": {"version": 1}
                            }
                        ]
                        for claim_response in bulk_request(methods, claims):
                            for action_response in claim_response:
                                f = lambda j: f"{j['claim_id']} - {j['status']}"
                                handle_response(action_response, f, check_claim=True)
                        continue

                    case Actions.REPORT:
                        if len(statuses) == 0:
                            statuses = []
                        claims = list(
                            set(find(interval=interval, pickup=pickup, statuses=statuses, date=date, action=command,
                                     final_client=len(clients) == which_client)))
                        continue

                    case Actions.FIND:
                        if Settings.PRODUCT == Products.EXPRESS:
                            claims = list(set(find(interval=interval, pickup=pickup, statuses=statuses)))
                        elif Settings.PRODUCT == Products.LOG_PLATFORM:
                            claims = list(set(find(date=" - ".join(interval), pickup=pickup, statuses=statuses)))
                        continue

                    case Actions.SAVE:
                        continue

                    case Actions.CLAIMS:
                        found_claims = []
                        if Settings.PRODUCT == Products.LOG_PLATFORM:
                            res = []
                            for claim in claims:
                                url = f"https://external-admin-proxy.taxi.yandex-team.ru/api/admin/api-proxy/logistic/api/admin/requests/list/"
                                headers = {"Authorization": f"OAuth {STAFF_TOKEN}", 'Content-Type': 'application/json',
                                           "X-Ya-Logistic-Cluster": "platform"}
                                get_params = {"limit": "50", "request_code": claim, "dump": "eventlog"}
                                response = requests.request("GET", url, data="", headers=headers, params=get_params)
                                response = response.json()

                                if len(response.get('history', '')) > 0:
                                    if response['history'][0].get('request_id', '') != '':
                                        request_id = response['history'][0].get('request_id', '')
                                        print(Fore.GREEN + request_id + Fore.RESET)
                                        res.append(request_id)

                            claims = list(set(res))
                            print(f"There are {len(claims)} requests found in total")
                        elif Settings.PRODUCT == Products.EXPRESS:
                            for external_order_id in claims:
                                search_response = make_request("claims/search", {
                                    "external_order_id": external_order_id,
                                    "limit": 1,
                                    "offset": 0
                                })
                                if 'claims' not in search_response.keys():
                                    print(f"{Fore.LIGHTRED_EX}{external_order_id}{Fore.RED} - not found{Fore.RESET}")
                                    continue
                                if len(search_response['claims']) == 0:
                                    print(f"{Fore.LIGHTRED_EX}{external_order_id}{Fore.RED} - not found{Fore.RESET}")
                                    continue
                                id = search_response['claims'][0]['id']
                                found_claims.append(id)
                                print(Fore.LIGHTGREEN_EX + id + Fore.RESET)

                        claims = list(set(found_claims))

                    case Actions.CANCEL:
                        if Settings.PRODUCT == Products.EXPRESS:
                            tasks = []

                            # td = TempData()
                            for claim in claims:
                                tasks.append(claims_cancel(claim))

                            await asyncio.gather(*tasks)
                            # claims = td.claims

                        elif Settings.PRODUCT == Products.LOG_PLATFORM:
                            for claim in claims:
                                response = make_request("request/cancel", {"request_id": claim})
                                f = lambda j: f"{claim} - {j['description']}"
                                handle_response(response, f)
                        continue
                    case Actions.DUPLICATES:
                        if len(statuses) == 0:
                            statuses = Statuses.all_statuses()
                        find(interval=interval, pickup=pickup, statuses=statuses, end_date=end_date, duplicates=True)

                        continue
                    case Actions.REORDER:
                        created_claims = []
                        if Settings.PRODUCT == Products.LOG_PLATFORM:
                            tasks = []

                            td = TempData()
                            for claim in claims:
                                tasks.append(lp_reorder(claim, td))

                            await asyncio.gather(*tasks)
                            claims = td.claims
                        else:
                            interval = {}
                            for claim in claims:
                                if len(claim) == 32:
                                    endpoint = f"claims/info?claim_id={claim}"
                                    payload = {}
                                else:
                                    endpoint = f"claims/search"
                                    payload = {
                                        "limit": 1,
                                        "offset": 0,
                                        "external_order_id": claim
                                    }
                                claim_info = make_request(endpoint, payload)
                                if 'claims' in claim_info.keys():
                                    if len(claim_info['claims']) > 0:
                                        claim_info = claim_info['claims'][0]

                                if interval == {} and sdd and 'same_day_data' not in interval.keys():
                                    try:
                                        print(
                                            f"{Fore.LIGHTYELLOW_EX}Getting information about starting point{Fore.RESET}")
                                        start_point = claim_info['route_points'][0]['address']['coordinates']
                                    except KeyError:
                                        start_point = [float(point) for point in
                                                       input(
                                                           f"{Fore.LIGHTRED_EX}Couldn't find a starting_point.{Fore.RESET} Specify here like {Fore.LIGHTBLUE_EX}12.34, 56.78{Fore.RESET}: ").split(
                                                           ", ")]

                                    print(f"{Fore.LIGHTYELLOW_EX}Requesting Same-day nearest interval{Fore.RESET}")
                                    delivery_methods = make_request("delivery-methods", {"start_point": start_point})

                                    if 'available_intervals' in delivery_methods['same_day_delivery'].keys() and len(
                                            delivery_methods['same_day_delivery']['available_intervals']) != 0:
                                        interval = delivery_methods['same_day_delivery']['available_intervals'][0]
                                        print(
                                            f"{Fore.LIGHTYELLOW_EX}The nearest interval requested is {interval}{Fore.RESET}\n")
                                    else:
                                        print(f"{Fore.LIGHTRED_EX}No available intervals for this client{Fore.RESET}")

                                if sdd:
                                    claim_info['same_day_data'] = {"delivery_interval": interval}
                                    if 'client_requirements' in claim_info.keys():
                                        del claim_info['client_requirements']

                                if 'route_points' in claim_info.keys():
                                    for route_point, a in enumerate(claim_info['route_points']):
                                        claim_info['route_points'][route_point]['point_id'] = \
                                            claim_info['route_points'][route_point]['id']

                                request_id = token_hex(16)

                                created_claim = claim
                                create_response = make_request(f"claims/create?request_id={request_id}", claim_info)

                                if 'id' in create_response.keys():
                                    created_claim = create_response['id']
                                    created_claims.append(created_claim)

                                f = lambda j: f"{created_claim}"
                                handle_response(create_response, f)

                            print(f"\n{Fore.LIGHTMAGENTA_EX}Approving claims{Fore.RESET}")
                            if len(created_claims) < 50:
                                time.sleep(3)

                            if len(created_claims) == 0:
                                print(f"\n{Fore.LIGHTRED_EX}Nothing to approve{Fore.RESET}")
                            for claim in created_claims:
                                accept_response = make_request(f"claims/accept?claim_id={claim}", {"version": 1})
                                f = lambda j: f"{j['id']} – accepted"
                                handle_response(accept_response, f)

                        if len(created_claims) > 0:
                            claims = list(set(created_claims))
                        continue
                    case Actions.REVERSED:
                        # for claim in claims:
                        #     iterations = 0
                        #     while True:
                        #         iterations += 1
                        #         if iterations > client_count * 2:
                        #             print(f"{Fore.LIGHTRED_EX}{claim} - unable to locate the client!{Fore.RESET}")
                        #             break
                        #         if i >= client_count:
                        #             i = 0
                        #         client_name, client_token = client_names[i], client_tokens[i]
                        #         found = False
                        #
                        #         try:
                        #             if len(claim) == 32:
                        #                 response = make_request(f"claims/info?claim_id={claim}", {},
                        #                                         different_token=client_token)
                        #             else:
                        #                 response = \
                        #                     make_request(f"claims/search",
                        #                                  {"external_order_id": claim, "limit": 5, "offset": 0},
                        #                                  different_token=client_token)['claims']
                        #                 temp = response[0]
                        #                 for claim_resp in response:
                        #                     if len(claim_resp['route_points']) in range(1, 4):
                        #                         response = claim_resp
                        #             found = True
                        #         except (KeyError, IndexError):
                        #             response = {}
                        #
                        #         if not found:
                        #             i += 1
                        #             continue
                        #         else:
                        #             data_to_send.append(response)
                        #             print(f"{Fore.LIGHTGREEN_EX}{claim} - {client_name}{Fore.RESET}")
                        #             break

                        # reversed_corp, route_scheme, different_A

                        if route_scheme == "":
                            route_scheme = "C - B - A"

                        letters = {"A": 0, "B": 1, "C": 2}
                        point_types = ["source", "destination", "return"]
                        created_claims = []

                        if isinstance(route_scheme, str):
                            route_scheme = route_scheme.split(" - ")

                        for claim in claims:
                            endpoint = f"claims/info?claim_id={claim}"
                            claim_info = make_request(endpoint, {})
                            claim_info_copy = copy.deepcopy(claim_info)

                            if len(claim_info['route_points']) > 3:
                                print(f"{Fore.LIGHTRED_EX}{claim} is a multi-stop delivery")
                                continue

                            if 'Second try' in claim_info.get('comment', ''):
                                print(Fore.LIGHTRED_EX + claim + " - " + "was already recreated")
                                continue

                            if 'status' not in claim_info.keys():
                                print(Fore.LIGHTRED_EX + claim + " - " + "not found")
                                continue

                            info = {
                                "A": claim_info['route_points'][0],
                                "B": claim_info['route_points'][1],
                                "C": claim_info['route_points'][2]
                            }

                            interval = {}
                            start_point = []

                            if len(different_A.split(", ")) > 1:
                                start_point = map(float, different_A.split(", "))
                            else:
                                start_point = info[route_scheme[0]]['address']['coordinates']

                            delivery_methods = make_request("delivery-methods", {"start_point": start_point})

                            if 'available_intervals' in delivery_methods['same_day_delivery'].keys() and len(
                                    delivery_methods['same_day_delivery']['available_intervals']) != 0:
                                interval = delivery_methods['same_day_delivery']['available_intervals'][0]
                            else:
                                print(
                                    f"{Fore.LIGHTRED_EX}No available intervals for this claim and point A{Fore.RESET}")

                            claim_info['same_day_data'] = {"delivery_interval": interval}
                            if 'client_requirements' in claim_info.keys():
                                del claim_info['client_requirements']

                            for i in range(3):
                                target_point = route_scheme[i]  # inherit from prev A, B or C
                                ancestor = copy.deepcopy(claim_info_copy['route_points'][letters[target_point]])
                                ancestor['type'] = point_types[i]

                                if ancestor['type'] == 'return':
                                    try:
                                        del ancestor['external_order_id']
                                    except KeyError:
                                        pass

                                ancestor['point_id'] = i + 1
                                ancestor['visit_order'] = i + 1
                                del ancestor['id']
                                claim_info['route_points'][i] = ancestor

                            for i in range(len(claim_info['items'])):
                                claim_info['items'][i] = {**claim_info['items'][i], **{"quantity": 1,
                                                                                       "weight": 1,
                                                                                       "size": {
                                                                                           "height": 0.1,
                                                                                           "length": 0.1,
                                                                                           "width": 0.1
                                                                                       },
                                                                                       "pickup_point": 1,
                                                                                       "droppof_point": 2
                                                                                       }}

                            request_id = token_hex(16)
                            claim_info['comment'] += " Second try"
                            create_response = make_request(f"claims/create?request_id={request_id}", claim_info)

                            created_claim = claim
                            if 'id' in create_response.keys():
                                created_claim = create_response['id']
                                created_claims.append(created_claim)

                            f = lambda j: f"{created_claim}"
                            handle_response(create_response, f)

                        time.sleep(3)
                        print(f"\n{Fore.LIGHTWHITE_EX}Accepting claims...")

                        if len(created_claims) == 0:
                            print(f"\n{Fore.LIGHTRED_EX}Nothing to approve{Fore.RESET}")

                        for claim in created_claims:
                            accept_response = make_request(f"claims/accept?claim_id={claim}", {"version": 1})
                            f = lambda j: f"{j['id']} – accepted"
                            handle_response(accept_response, f)

                        claims = list(set(created_claims))

                        continue
                    case Actions.SORTING_FILE:
                        if len(statuses) == 0:
                            statuses = Statuses.ROUTED
                        find(interval=interval, pickup=pickup, statuses=statuses)
                        continue
                    case Actions.SCANNED:
                        continue
                    case _:
                        print(
                            f"{Fore.LIGHTMAGENTA_EX}There is no action {Fore.RESET}{command}{Fore.LIGHTRED_EX} created. Please try again.{Fore.RESET}")
                        continue

            if claims != original_claims:
                todo_claims[client] = claims
            claims = deepcopy(todo_claims) if todo_claims != {} else claims
    except KeyboardInterrupt:
        print(f"\n\n{Fore.LIGHTRED_EX}The application was forced to be stopped by the keyboard{Fore.RESET}")


asyncio.run(main())
