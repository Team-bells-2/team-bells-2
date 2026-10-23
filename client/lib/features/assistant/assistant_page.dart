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
  SpeechToText? _speech;
  var _listening = false;

  @override
  void dispose() {
    _composer.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _send(String raw) {
    final text = raw.trim();
    if (text.isEmpty) return;
    _composer.clear();
    widget.book.send(text);
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
    if (_listening) {
      await _speech?.stop();
      if (!mounted) return;
      setState(() => _listening = false);
      _send(_composer.text);
      return;
    }

    _speech ??= SpeechToText();
    try {
      final ready = await _speech!.initialize(
        onStatus: (status) {
          if (!mounted) return;
          if (status == 'done' || status == 'notListening') {
            setState(() => _listening = false);
          }
        },
      );
      if (!ready) {
        _voiceUnavailable();
        return;
      }
      if (!mounted) return;
      setState(() => _listening = true);
      await _speech!.listen(
        onResult: (result) {
          if (!mounted) return;
          _composer.value = TextEditingValue(
            text: result.recognizedWords,
            selection: TextSelection.collapsed(offset: result.recognizedWords.length),
          );
          setState(() {});
          if (result.finalResult) _send(result.recognizedWords);
        },
        listenOptions: SpeechListenOptions(
          listenMode: ListenMode.dictation,
          partialResults: true,
          cancelOnError: true,
          listenFor: const Duration(seconds: 12),
          pauseFor: const Duration(seconds: 3),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => _listening = false);
      _voiceUnavailable();
    }
  }

  void _voiceUnavailable() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(backgroundColor: ojaGreen, content: Text('Voice is not available here. Type the message.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final showSamples = widget.book.lines.length == 1;
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
                      onPressed: () => _send(sample),
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
        if (_listening)
          const Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text('Listening…', style: TextStyle(color: ojaGreen, fontWeight: FontWeight.w600)),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
          child: Row(
            children: [
              IconButton(
                tooltip: _listening ? 'Stop' : 'Speak',
                onPressed: _toggleMic,
                style: IconButton.styleFrom(backgroundColor: ojaGreen, foregroundColor: Colors.white),
                icon: Icon(_listening ? Icons.stop : Icons.mic),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  key: const Key('composer'),
                  controller: _composer,
                  textInputAction: TextInputAction.send,
                  onSubmitted: _send,
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
                onPressed: () => _send(_composer.text),
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
