import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';

class OjaApiException implements Exception {
  OjaApiException(this.statusCode, this.message, {this.code});

  final int statusCode;
  final String message;

  /// The server's `error.code`, e.g. `phone_taken`, `invalid_credentials` or `ai_unavailable`.
  final String? code;

  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() => message;
}

/// Client for the OJA API in `server/` (see FRONTEND_HANDOFF.md).
///
/// Trader calls send `Authorization: Bearer <token>`. The token comes from [signUp] or [logIn]
/// and is saved on the phone, so the trader stays logged in after the app closes.
class OjaApi {
  OjaApi({this.baseUrl = ojaApiBaseUrl, HttpClient? client}) : _client = client ?? HttpClient();

  static const _tokenKey = 'oja_session_token';
  static const _traderKey = 'oja_trader';

  final String baseUrl;
  final HttpClient _client;
  final _random = Random();
  String? _token;

  /// The signed-in trader (`name`, `phone`, `business_name`, `location_name`, ...).
  Map<String, dynamic>? trader;

  bool get signedIn => _token != null;

  /// Loads a saved session from the phone. Returns true when one exists.
  Future<bool> restoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_tokenKey);
    final saved = prefs.getString(_traderKey);
    trader = saved == null ? null : Map<String, dynamic>.from(jsonDecode(saved) as Map);
    return _token != null;
  }

  /// Creates the trader with their main items and logs them in.
  Future<void> signUp({
    required String name,
    required String phone,
    required String businessName,
    required String pin,
    required String market,
  }) async {
    final result = await _postJson('/onboarding', {
      'name': name,
      'phone': phone,
      'business_name': businessName,
      'sector': 'foodstuff',
      'location_name': market,
      'pin': pin,
      'items': ojaStartingItems,
    }, auth: false);
    await _saveSession(result);
  }

  Future<void> logIn({required String phone, required String pin}) async {
    final result = await _postJson('/auth/login', {'phone': phone, 'pin': pin}, auth: false);
    await _saveSession(result);
  }

  /// Ends this phone's session on the server (best effort) and forgets it locally.
  Future<void> logOut() async {
    try {
      if (_token != null) await _send('POST', '/auth/logout');
    } on OjaApiException {
      // The local session is cleared either way.
    }
    await clearSession();
  }

  Future<void> clearSession() async {
    _token = null;
    trader = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_traderKey);
  }

  Future<void> _saveSession(Map<String, dynamic> result) async {
    _token = result['token'] as String?;
    trader = result['trader'] is Map ? Map<String, dynamic>.from(result['trader'] as Map) : null;
    final prefs = await SharedPreferences.getInstance();
    if (_token != null) await prefs.setString(_tokenKey, _token!);
    if (trader != null) await prefs.setString(_traderKey, jsonEncode(trader));
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

  /// The assistant chat, oldest first (`role` is `trader` or `assistant`).
  Future<Map<String, dynamic>> getChatHistory({int limit = 200}) => _getJson('/messages/history?limit=$limit');

  Future<Map<String, dynamic>> ask(String question) => _postJson('/ask', {'question': question});

  /// Text message (typed, or speech recognised on the phone): the server saves,
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

  Future<Object?> _send(String method, String path, {Map<String, dynamic>? payload, bool auth = true}) async {
    if (auth && _token == null) {
      throw OjaApiException(401, 'Please log in.', code: 'missing_token');
    }
    final uri = Uri.parse('$baseUrl$path');
    late final HttpClientResponse response;
    try {
      final request = method == 'POST' ? await _client.postUrl(uri) : await _client.getUrl(uri);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (auth) request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_token');
      if (payload != null) {
        request.headers.contentType = ContentType.json;
        request.add(utf8.encode(jsonEncode(payload)));
      }
      // Render's free plan sleeps when idle; the first call after that can take about a minute.
      response = await request.close().timeout(const Duration(seconds: 90));
    } on SocketException catch (error) {
      throw OjaApiException(0, 'Cannot reach OJA. Check your internet. (${error.message})');
    } on HttpException catch (error) {
      throw OjaApiException(0, 'Cannot reach OJA. Check your internet. (${error.message})');
    } on TimeoutException {
      throw OjaApiException(0, 'OJA is taking too long to answer. Try again.');
    }

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
        (error['message'] as String?) ?? 'Something went wrong (${response.statusCode}).',
        code: error['code'] as String?,
      );
    }
    throw OjaApiException(response.statusCode, 'Something went wrong (${response.statusCode}).');
  }

  void close() => _client.close(force: true);
}
