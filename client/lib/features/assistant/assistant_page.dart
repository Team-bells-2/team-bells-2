import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../core/ledger/ledger.dart';
import '../../core/theme.dart';

const _samples = [
  'I sell 2.5 bags rice for Mama Ngozi 60k',
  'Who owes me?',
  'Where I fit buy rice?',
];

class AssistantPage extends StatefulWidget {
  const AssistantPage({super.key, required this.book, required this.onChanged});

  final OjaBook book;
  final VoidCallback onChanged;

  @override
  State<AssistantPage> createState() => _AssistantPageState();
}

class _AssistantPageState extends State<AssistantPage> {
  final _composer = TextEditingController();
  final _scroll = ScrollController();
  // Speech is recognised on the phone and sent as text, so voice works without a server
  // speech-to-text key. `_recording` is true while the phone is listening.
  final _speech = SpeechToText();
  var _speechReady = false;
  var _recording = false;
  final _transcribing = false;

  @override
  void dispose() {
    _composer.dispose();
    _scroll.dispose();
    _speech.cancel();
    super.dispose();
  }

  Future<void> _send(String raw, {bool fromVoice = false}) async {
    final text = raw.trim();
    if (text.isEmpty || widget.book.busy || _transcribing) return;
    _composer.clear();
    setState(() {});
    await widget.book.sendAsync(text, fromVoice: fromVoice);
    if (!mounted) return;
    widget.onChanged();
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _toggleMic() async {
    if (widget.book.busy) return;

    if (_recording) {
      // Stop: the final result arrives in onResult and is sent from there.
      await _speech.stop();
      if (mounted) setState(() => _recording = false);
      return;
    }

    try {
      _speechReady = _speechReady ||
          await _speech.initialize(
            onStatus: (status) {
              if (!mounted) return;
              if (status == 'done' || status == 'notListening') setState(() => _recording = false);
            },
            onError: (error) {
              if (!mounted) return;
              setState(() => _recording = false);
              if (error.errorMsg == 'error_no_match' || error.errorMsg == 'error_speech_timeout') {
                _snack('I did not hear anything. Tap the mic and talk again.');
              }
            },
          );
    } catch (_) {
      _speechReady = false;
    }
    if (!_speechReady) {
      _snack('Voice is not available. Allow the microphone in Settings, or type the message.');
      return;
    }

    if (!mounted) return;
    setState(() => _recording = true);
    await _speech.listen(
      onResult: (result) {
        if (!mounted) return;
        _composer.value = TextEditingValue(
          text: result.recognizedWords,
          selection: TextSelection.collapsed(offset: result.recognizedWords.length),
        );
        setState(() {});
        if (result.finalResult && result.recognizedWords.trim().isNotEmpty) {
          setState(() => _recording = false);
          _send(result.recognizedWords, fromVoice: true);
        }
      },
      listenOptions: SpeechListenOptions(
        listenMode: ListenMode.dictation,
        partialResults: true,
        cancelOnError: true,
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 4),
      ),
    );
  }

  void _snack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(backgroundColor: ojaGreen, content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final showSamples = widget.book.lines.length == 1;
    final micBusy = widget.book.busy || _transcribing;
    return Column(
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text('Assistant', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ojaInk)),
          ),
        ),
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            itemCount: widget.book.lines.length,
            itemBuilder: (context, index) {
              final line = widget.book.lines[index];
              return _Bubble(fromTrader: line.fromTrader, text: line.text);
            },
          ),
        ),
        if (showSamples)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final sample in _samples)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: OutlinedButton(
                      onPressed: micBusy ? null : () => _send(sample),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: ojaGreen,
                        side: const BorderSide(color: ojaGreen),
                        alignment: Alignment.centerLeft,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      ),
                      child: Text(sample),
                    ),
                  ),
              ],
            ),
          ),
        if (_recording)
          const Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text('Recording… tap stop when done', style: TextStyle(color: ojaGreen, fontWeight: FontWeight.w600)),
          ),
        if (_transcribing)
          const Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text('Transcribing on server…', style: TextStyle(color: ojaGreen, fontWeight: FontWeight.w600)),
          ),
        if (widget.book.busy)
          const Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text('Talking to OJA…', style: TextStyle(color: ojaGreen, fontWeight: FontWeight.w600)),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
          child: Row(
            children: [
              IconButton(
                tooltip: _recording ? 'Stop' : 'Speak',
                onPressed: micBusy && !_recording ? null : _toggleMic,
                style: IconButton.styleFrom(
                  backgroundColor: _recording ? ojaOut : ojaGreen,
                  foregroundColor: Colors.white,
                ),
                icon: Icon(_recording ? Icons.stop : Icons.mic),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  key: const Key('composer'),
                  controller: _composer,
                  enabled: !micBusy && !_recording,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (value) => _send(value),
                  style: const TextStyle(color: ojaInk),
                  decoration: InputDecoration(
                    hintText: 'Speak or type',
                    hintStyle: const TextStyle(color: ojaMuted),
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: const BorderSide(color: ojaLine)),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: const BorderSide(color: ojaLine)),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: const BorderSide(color: ojaGreen, width: 1.5),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                key: const Key('send'),
                tooltip: 'Send',
                onPressed: micBusy || _recording ? null : () => _send(_composer.text),
                style: IconButton.styleFrom(backgroundColor: ojaGreen, foregroundColor: Colors.white),
                icon: const Icon(Icons.arrow_upward),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.fromTrader, required this.text});

  final bool fromTrader;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: fromTrader ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 320),
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: fromTrader ? ojaGreen : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: fromTrader ? null : Border.all(color: ojaLine),
        ),
        child: Text(text, style: TextStyle(color: fromTrader ? Colors.white : ojaInk, height: 1.35)),
      ),
    );
  }
}
