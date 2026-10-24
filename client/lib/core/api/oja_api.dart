import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'config.dart';

class OjaApiException implements Exception {
  OjaApiException(this.statusCode, this.message, {this.code});

  final int statusCode;
  final String message;

  /// The server's `error.code`, e.g. `ai_unavailable` or `invalid_credentials`.
  final String? code;

  @override
  String toString() => message;
}

/// Client for the OJA API in `server/` (see FRONTEND_HANDOFF.md).
///
/// Every trader call sends `Authorization: Bearer <token>`. The token comes from
/// [signIn]: log in with phone + PIN, or onboard the trader the first time.
class OjaApi {
  OjaApi({this.baseUrl = ojaApiBaseUrl, HttpClient? client}) : _client = client ?? HttpClient();

  final String baseUrl;
  final HttpClient _client;
  final _random = Random();
  String? _token;

  bool get signedIn => _token != null;

  /// Logs in with the configured phone + PIN. When the trader does not exist yet,
  /// onboards them with their main items, then keeps the returned token.
  Future<Map<String, dynamic>> signIn() async {
    try {
      final result = await _postJson('/auth/login', {'phone': ojaTraderPhone, 'pin': ojaTraderPin}, auth: false);
      _token = result['token'] as String?;
      return Map<String, dynamic>.from(result['trader'] as Map);
    } on OjaApiException catch (error) {
      if (error.code != 'invalid_credentials') rethrow;
    }
    final result = await _postJson('/onboarding', {
      'name': ojaTraderName,
      'phone': ojaTraderPhone,
      'business_name': ojaBusinessName,
      'sector': 'foodstuff',
      'location_name': ojaLocationName,
      'pin': ojaTraderPin,
      'items': ojaStartingItems,
    }, auth: false);
    _token = result['token'] as String?;
    return Map<String, dynamic>.from(result['trader'] as Map);
  }

  Future<Map<String, dynamic>> getHome({String period = 'today'}) => _getJson('/home?period=$period');

  Future<List<Map<String, dynamic>>> getEntries({String? period, int limit = 50}) {
    final query = period == null ? 'limit=$limit' : 'period=$period&limit=$limit';
    return _getJsonList('/entries?$query');
  }

  Future<List<Map<String, dynamic>>> getCustomers() => _getJsonList('/customers');

  Future<List<Map<String, dynamic>>> getInventory() => _getJsonList('/inventory');

  /// Up to 3 restock suppliers. Without [quantity] the item's reorder quantity is used.
  Future<Map<String, dynamic>> getSuggestions(String item, {double? quantity}) {
    final query = 'item=${Uri.encodeQueryComponent(item)}${quantity == null ? '' : '&quantity=$quantity'}';
    return _getJson('/suggestions?$query');
  }

  Future<Map<String, dynamic>> ask(String question) => _postJson('/ask', {'question': question});

  /// Text message (typed, or a voice note transcribed on the phone): the server saves,
  /// corrects, asks one question or falls back. Reuse [clientMessageId] on a retry.
  Future<Map<String, dynamic>> sendMessage(String text, {String? clientMessageId}) {
    return _postJson('/messages', {'text': text, 'client_message_id': clientMessageId ?? newMessageId()});
  }

  String newMessageId() =>
      '${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}-${_random.nextInt(1 << 32).toRadixString(36)}';

  Future<Map<String, dynamic>> _getJson(String path) async {
    final body = await _send('GET', path);
    if (body is Map<String, dynamic>) return body;
    throw OjaApiException(500, 'Unexpected response from $path.');
  }

  Future<List<Map<String, dynamic>>> _getJsonList(String path) async {
    final body = await _send('GET', path);
    if (body is List) {
      return body.map((item) => Map<String, dynamic>.from(item as Map)).toList();
    }
    throw OjaApiException(500, 'Unexpected list response from $path.');
  }

  Future<Map<String, dynamic>> _postJson(String path, Map<String, dynamic> payload, {bool auth = true}) async {
    final body = await _send('POST', path, payload: payload, auth: auth);
    if (body is Map<String, dynamic>) return body;
    throw OjaApiException(500, 'Unexpected response from $path.');
  }

  /// Sends one request. A 401 on a trader call (expired or unknown token) signs in again once and retries.
  Future<Object?> _send(String method, String path, {Map<String, dynamic>? payload, bool auth = true}) async {
    if (auth && _token == null) await signIn();
    try {
      return await _sendOnce(method, path, payload: payload, auth: auth);
    } on OjaApiException catch (error) {
      if (!auth || error.statusCode != 401) rethrow;
      _token = null;
      await signIn();
      return _sendOnce(method, path, payload: payload, auth: auth);
    }
  }

  Future<Object?> _sendOnce(String method, String path, {Map<String, dynamic>? payload, required bool auth}) async {
    final uri = Uri.parse('$baseUrl$path');
    late final HttpClientRequest request;
    try {
      request = method == 'POST' ? await _client.postUrl(uri) : await _client.getUrl(uri);
    } on SocketException catch (error) {
      throw OjaApiException(0, 'Cannot reach OJA API: ${error.message}');
    }

    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    if (auth && _token != null) {
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_token');
    }
    if (payload != null) {
      request.headers.contentType = ContentType.json;
      request.add(utf8.encode(jsonEncode(payload)));
    }

    // Render's starter instance can take a while on the first call after a deploy.
    final response = await request.close().timeout(const Duration(seconds: 60));
    final raw = await response.transform(utf8.decoder).join();
    Object? decoded;
    if (raw.isNotEmpty) {
      try {
        decoded = jsonDecode(raw);
      } on FormatException {
        decoded = null;
      }
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return decoded;
    }

    final error = decoded is Map ? decoded['error'] : null;
    if (error is Map) {
      throw OjaApiException(
        response.statusCode,
        (error['message'] as String?) ?? 'API error (${response.statusCode}).',
        code: error['code'] as String?,
      );
    }
    throw OjaApiException(response.statusCode, 'API error (${response.statusCode}).');
  }

  void close() => _client.close(force: true);
}
