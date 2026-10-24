import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/api/config.dart';
import '../../core/api/oja_api.dart';
import '../../core/theme.dart';

/// Create an account (name, phone, business name, PIN, market) or log in with phone + PIN.
class AuthPage extends StatefulWidget {
  const AuthPage({super.key, required this.api, required this.onSignedIn});

  final OjaApi api;
  final VoidCallback onSignedIn;

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _business = TextEditingController();
  final _pin = TextEditingController();
  var _signUp = true;
  var _busy = false;
  String? _market;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _business.dispose();
    _pin.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      if (_signUp) {
        await widget.api.signUp(
          name: _name.text.trim(),
          phone: _phone.text.trim(),
          businessName: _business.text.trim(),
          pin: _pin.text.trim(),
          market: _market!,
        );
      } else {
        await widget.api.logIn(phone: _phone.text.trim(), pin: _pin.text.trim());
      }
      if (!mounted) return;
      widget.onSignedIn();
    } on OjaApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _friendly(OjaApiException error) {
    return switch (error.code) {
      'phone_taken' => 'This phone number already has an account. Log in instead.',
      'invalid_credentials' => 'Phone number or PIN is wrong.',
      'account_locked' => 'Too many wrong PINs. Wait 5 minutes and try again.',
      'unknown_location' => 'Choose your market from the list.',
      _ => error.message,
    };
  }

  void _switchMode() {
    setState(() {
      _signUp = !_signUp;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ojaPage,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text('OJA', style: TextStyle(color: ojaGreen, fontSize: 28, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 4),
                    Text(
                      _signUp ? 'Create your account' : 'Welcome back',
                      style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: ojaInk),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _signUp ? 'Speak or type your sales. Your books write themselves.' : 'Log in with your phone number and PIN.',
                      style: const TextStyle(color: ojaMuted),
                    ),
                    const SizedBox(height: 20),
                    if (_signUp) ...[
                      _field(
                        key: const Key('auth-name'),
                        controller: _name,
                        label: 'Your name',
                        validator: (v) => _required(v, 'Enter your name.'),
                        textCapitalization: TextCapitalization.words,
                      ),
                      const SizedBox(height: 12),
                    ],
                    _field(
                      key: const Key('auth-phone'),
                      controller: _phone,
                      label: 'Phone number',
                      hint: '08012345678',
                      keyboardType: TextInputType.phone,
                      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9+]'))],
                      validator: (v) {
                        final value = (v ?? '').trim();
                        if (value.length < 7 || value.length > 20) return 'Enter a valid phone number.';
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),
                    if (_signUp) ...[
                      _field(
                        key: const Key('auth-business'),
                        controller: _business,
                        label: 'Business name',
                        hint: 'e.g. Ada Foods',
                        validator: (v) => _required(v, 'Enter your business name.'),
                        textCapitalization: TextCapitalization.words,
                      ),
                      const SizedBox(height: 12),
                    ],
                    _field(
                      key: const Key('auth-pin'),
                      controller: _pin,
                      label: _signUp ? 'Choose a PIN (4 to 6 digits)' : 'PIN',
                      keyboardType: TextInputType.number,
                      obscureText: true,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
                      validator: (v) {
                        final value = (v ?? '').trim();
                        if (value.length < 4 || value.length > 6) return 'PIN must be 4 to 6 digits.';
                        return null;
                      },
                    ),
                    if (_signUp) ...[
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String>(
                        key: const Key('auth-market'),
                        initialValue: _market,
                        decoration: _decoration('Your market'),
                        items: [for (final m in ojaMarkets) DropdownMenuItem(value: m, child: Text(m))],
                        onChanged: _busy ? null : (value) => setState(() => _market = value),
                        validator: (v) => v == null ? 'Choose your market.' : null,
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 14),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(color: const Color(0xFFFDEDE7), borderRadius: BorderRadius.circular(12)),
                        child: Text(_error!, key: const Key('auth-error'), style: const TextStyle(color: ojaOut)),
                      ),
                    ],
                    const SizedBox(height: 20),
                    FilledButton(
                      key: const Key('auth-submit'),
                      onPressed: _busy ? null : _submit,
                      style: FilledButton.styleFrom(
                        backgroundColor: ojaGreen,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      child: _busy
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
                            )
                          : Text(_signUp ? 'Create account' : 'Log in', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      key: const Key('auth-switch'),
                      onPressed: _busy ? null : _switchMode,
                      style: TextButton.styleFrom(foregroundColor: ojaGreenDark),
                      child: Text(_signUp ? 'I already have an account. Log in' : 'New to OJA? Create an account'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  String? _required(String? value, String message) => (value ?? '').trim().isEmpty ? message : null;

  InputDecoration _decoration(String label, {String? hint}) {
    OutlineInputBorder border(Color color, [double width = 1]) =>
        OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: color, width: width));
    return InputDecoration(
      labelText: label,
      hintText: hint,
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: border(ojaLine),
      enabledBorder: border(ojaLine),
      focusedBorder: border(ojaGreen, 1.5),
    );
  }

  Widget _field({
    required Key key,
    required TextEditingController controller,
    required String label,
    String? hint,
    TextInputType? keyboardType,
    bool obscureText = false,
    List<TextInputFormatter>? inputFormatters,
    String? Function(String?)? validator,
    TextCapitalization textCapitalization = TextCapitalization.none,
  }) {
    return TextFormField(
      key: key,
      controller: controller,
      enabled: !_busy,
      keyboardType: keyboardType,
      obscureText: obscureText,
      inputFormatters: inputFormatters,
      textCapitalization: textCapitalization,
      validator: validator,
      style: const TextStyle(color: ojaInk),
      decoration: _decoration(label, hint: hint),
    );
  }
}
