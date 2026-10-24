import 'dart:convert';
import 'dart:io';

import 'config.dart';

class OjaApiException implements Exception {
  OjaApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  @override
  String toString() => message;
}

/// Thin client for the live Render API (`backend.py` contract).
///
/// Text ledger writes use [createEntry] (`POST /entries`).
/// Voice uses [transcribe] then [sendMessage] (`/transcribe`, `/messages`).
class OjaApi {
  OjaApi({this.baseUrl = ojaApiBaseUrl, HttpClient? client}) : _client = client ?? HttpClient();

  final String baseUrl;
  final HttpClient _client;

  Future<Map<String, dynamic>> getProfit() async {
    return _getJson('/reports/profit');
  }

  Future<Map<String, dynamic>> getInsights() async {
    return _getJson('/insights');
  }

  Future<List<Map<String, dynamic>>> getCustomers() async {
    return _getJsonList('/customers');
  }

  Future<List<Map<String, dynamic>>> getEntries({int limit = 50}) async {
    return _getJsonList('/entries?limit=$limit');
  }

  Future<List<Map<String, dynamic>>> getInventory() async {
    return _getJsonList('/inventory');
  }

  Future<Map<String, dynamic>> getMarkets() async {
    return _getJson('/markets');
  }

  Future<Map<String, dynamic>> recommendMarkets({
    required String product,
    required double quantity,
    String priority = 'balanced',
  }) async {
    return _postJson('/markets/recommend', {
      'product': product,
      'quantity': quantity,
      'priority': priority,
    });
  }

  Future<Map<String, dynamic>> ask(String question) async {
    return _postJson('/ask', {'question': question});
  }

  /// Structured text entry — use for typed assistant input.
  Future<Map<String, dynamic>> createEntry(Map<String, dynamic> entry) async {
    return _postJson('/entries', entry);
  }

  Future<Map<String, dynamic>> stockIn(Map<String, dynamic> body) async {
    return _postJson('/inventory/stock-in', body);
  }

  /// AI / conversation path — use after voice transcription.
  Future<Map<String, dynamic>> sendMessage({
    required String text,
    required String conversationId,
  }) async {
    return _postJson('/messages', {
      'text': text,
      'conversation_id': conversationId,
    });
  }

  /// Upload raw audio bytes to local Whisper on the server.
  Future<Map<String, dynamic>> transcribe(List<int> audio, {String contentType = 'audio/m4a'}) async {
    final uri = Uri.parse('$baseUrl/transcribe');
    late final HttpClientRequest request;
    try {
      request = await _client.postUrl(uri);
    } on SocketException catch (error) {
      throw OjaApiException(0, 'Cannot reach OJA API: ${error.message}');
    }
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    request.headers.set(HttpHeaders.contentTypeHeader, contentType);
    request.add(audio);
    final response = await request.close().timeout(const Duration(seconds: 90));
    final raw = await response.transform(utf8.decoder).join();
    final decoded = raw.isEmpty ? null : jsonDecode(raw);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (decoded is Map<String, dynamic>) return decoded;
      throw OjaApiException(500, 'Unexpected response from /transcribe.');
    }
    throw OjaApiException(response.statusCode, _errorMessage(decoded, response.statusCode));
  }

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

  Future<Map<String, dynamic>> _postJson(String path, Map<String, dynamic> payload) async {
    final body = await _send('POST', path, payload: payload);
    if (body is Map<String, dynamic>) return body;
    throw OjaApiException(500, 'Unexpected response from $path.');
  }

  Future<Object?> _send(String method, String path, {Map<String, dynamic>? payload}) async {
    final uri = Uri.parse('$baseUrl$path');
    late final HttpClientRequest request;
    try {
      request = method == 'POST' ? await _client.postUrl(uri) : await _client.getUrl(uri);
    } on SocketException catch (error) {
      throw OjaApiException(0, 'Cannot reach OJA API: ${error.message}');
    }

    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    if (payload != null) {
      request.headers.contentType = ContentType.json;
      request.add(utf8.encode(jsonEncode(payload)));
    }

    final response = await request.close().timeout(const Duration(seconds: 60));
    final raw = await response.transform(utf8.decoder).join();
    Object? decoded;
    if (raw.isNotEmpty) {
      decoded = jsonDecode(raw);
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return decoded;
    }

    throw OjaApiException(response.statusCode, _errorMessage(decoded, response.statusCode));
  }

  String _errorMessage(Object? decoded, int statusCode) {
    if (decoded is Map) {
      final detail = decoded['detail'];
      if (detail is String && detail.isNotEmpty) return detail;
      if (detail is Map && detail['message'] is String) return detail['message'] as String;
      if (detail is List && detail.isNotEmpty) {
        final first = detail.first;
        if (first is Map && first['msg'] is String) return first['msg'] as String;
        return detail.toString();
      }
      if (decoded['message'] is String) return decoded['message'] as String;
    }
    return 'API error ($statusCode).';
  }

  void close() => _client.close(force: true);
}
