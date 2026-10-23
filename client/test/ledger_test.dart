import 'package:flutter_test/flutter_test.dart';
import 'package:oja/core/ledger/ledger.dart';

void main() {
  test('a sale with an amount is saved from the words', () {
    final book = OjaBook();

    book.send('I sell two bags and half rice for Mama Ngozi sixty k');

    expect(book.entries, hasLength(1));
    final entry = book.entries.single;
    expect(entry.kind, EntryKind.creditSale);
    expect(entry.quantity, 2.5);
    expect(entry.itemKey, 'rice');
    expect(entry.customer, 'Mama Ngozi');
    expect(entry.amountNgn, 60000);
    expect(book.lines.last.text, contains('₦60,000'));
    expect(book.stock['rice'], 7.5);
  });

  test('a missing amount asks one question, then the answer saves it', () {
    final book = OjaBook();

    book.send('I sell two bags and half');

    expect(book.entries, isEmpty);
    expect(book.lines.last.text, 'How much did you collect for the 2.5 bags?');

    book.send('sixty k');

    expect(book.entries, hasLength(1));
    expect(book.entries.single.amountNgn, 60000);
    expect(book.entries.single.quantity, 2.5);
  });

  test('a correction updates the same entry and the stock', () {
    final book = OjaBook();
    book.send('I sell two bags and half rice for Mama Ngozi sixty k');
    final id = book.entries.single.id;

    book.send('No, I mean four bags');

    expect(book.entries, hasLength(1));
    expect(book.entries.single.id, id);
    expect(book.entries.single.quantity, 4);
    expect(book.stock['rice'], 6);
    expect(book.lines.last.text, startsWith('Updated'));
  });

  test('a nickname payment reduces what is owed', () {
    final book = OjaBook();
    book.send('I sell 2 bags rice for Mama Ngozi 60k');
    book.send('The rice woman don pay thirty k');

    expect(book.balanceOf('Mama Ngozi'), 30000);
    book.send('Who owes me?');
    expect(book.lines.last.text, 'Mama Ngozi owes ₦30,000.');
    expect(book.sales, 60000);
    expect(book.profit, 60000);
  });

  test('shorthand amounts and a buy that restocks', () {
    final book = OjaBook();

    book.send('I sell 1 bag rice ten k');
    book.send('I sell 1 bag beans 2.5k');
    book.send('I buy 5 bags rice 40k');

    expect(book.entries[0].amountNgn, 10000);
    expect(book.entries[1].amountNgn, 2500);
    expect(book.entries[2].kind, EntryKind.expense);
    expect(book.stock['rice'], 10 - 1 + 5);
    expect(book.expenses, 40000);
    expect(book.profit, 12500 - 40000);
  });

  test('gibberish does not create an entry', () {
    final book = OjaBook();

    book.send('asdf qwer');

    expect(book.entries, isEmpty);
    expect(book.lines.last.text, contains('did not catch'));
  });

  test('the demo day matches the home card', () {
    final book = OjaBook.demo();

    expect(book.cashSales, 50000);
    expect(book.creditSales, 60000);
    expect(book.sales, 110000);
    expect(book.expenses, 40000);
    expect(book.profit, 70000);
    expect(book.owed, 30000);
    expect(book.stock['rice'], 2);
  });

  test('market ranking prefers suppliers who can fill the order', () {
    final rice = rankOffers('rice');

    expect(rice.first.offer.supplier, 'Alhaji Musa Grains');
    expect(rice.map((row) => row.offer.supplier), isNot(contains('Short Stock Shed')));
    expect(rankOffers('garri').last.offer.supplier, 'Farmside Garri');

    final book = OjaBook();
    book.send('Where I fit buy rice?');
    expect(book.marketItem, 'rice');
    expect(book.lines.last.text, contains('Alhaji Musa Grains'));
  });
}
