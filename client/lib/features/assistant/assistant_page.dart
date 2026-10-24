import 'dart:io';

import 'package:flutter/material.dart';
import 'package:record/record.dart';

import '../../core/api/oja_api.dart';
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
  final _recorder = AudioRecorder();
  var _recording = false;
  var _transcribing = false;

  @override
  void dispose() {
    _composer.dispose();
    _scroll.dispose();
    _recorder.dispose();
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
    if (!widget.book.isLive) {
      _snack('Connect to the live API to use server transcription.');
      return;
    }
    if (_transcribing || widget.book.busy) return;

    if (_recording) {
      await _stopAndTranscribe();
      return;
    }

    final allowed = await _recorder.hasPermission();
    if (!allowed) {
      _snack('Microphone permission is required. Allow it in Settings.');
      return;
    }

    try {
      final path = '${Directory.systemTemp.path}/oja_voice_${DateTime.now().millisecondsSinceEpoch}.wav';
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          numChannels: 1,
          sampleRate: 16000,
        ),
        path: path,
      );
      if (!mounted) return;
      setState(() => _recording = true);
    } catch (_) {
      if (!mounted) return;
      setState(() => _recording = false);
      _snack('Could not start the microphone. Try again.');
    }
  }

  Future<void> _stopAndTranscribe() async {
    String? path;
    try {
      path = await _recorder.stop();
    } catch (_) {
      path = null;
    }
    if (!mounted) return;
    setState(() {
      _recording = false;
      _transcribing = true;
    });

    if (path == null || path.isEmpty) {
      setState(() => _transcribing = false);
      _snack('No audio captured. Hold a bit longer, then stop.');
      return;
    }

    final file = File(path);
    try {
      final bytes = await file.readAsBytes();
      if (bytes.isEmpty) {
        _snack('Recording was empty. Try again.');
        return;
      }
      final transcript = await widget.book.transcribeAudio(bytes, contentType: 'audio/wav');
      if (!mounted) return;
      _composer.text = transcript;
      setState(() => _transcribing = false);
      await _send(transcript, fromVoice: true);
    } on OjaApiException catch (error) {
      if (!mounted) return;
      _snack(error.message);
    } catch (_) {
      if (!mounted) return;
      _snack('Transcription failed. Type the message instead.');
    } finally {
      try {
        if (await file.exists()) await file.delete();
      } catch (_) {}
      if (mounted) setState(() => _transcribing = false);
    }
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
