import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:oja/app/oja_app.dart';

void main() {
  testWidgets('home shows the day, and the assistant can answer who owes', (tester) async {
    await tester.pumpWidget(const OjaApp());

    expect(find.text('Iya Basira'), findsOneWidget);
    expect(find.text('₦110,000'), findsOneWidget);
    expect(find.textContaining('₦70,000'), findsOneWidget);
    await tester.scrollUntilVisible(find.textContaining('Rice is low'), 300);
    expect(find.textContaining('Rice is low'), findsOneWidget);

    await tester.tap(find.byKey(const Key('tab-assistant')));
    await tester.pump();

    await tester.enterText(find.byKey(const Key('composer')), 'Who owes me?');
    await tester.tap(find.byKey(const Key('send')));
    await tester.pumpAndSettle();

    expect(find.textContaining('Mama Ngozi owes ₦30,000'), findsOneWidget);

    await tester.tap(find.byKey(const Key('tab-inventory')));
    await tester.pump();

    expect(find.text('Alhaji Musa Grains'), findsOneWidget);
  });
}
