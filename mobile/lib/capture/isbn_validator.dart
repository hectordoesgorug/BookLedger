class IsbnValidator {
  const IsbnValidator._();

  static String? normalizeAndValidate(String? input) {
    if (input == null) {
      return null;
    }

    final compact = input
        .replaceAll(RegExp(r'ISBN(?:-1[03])?', caseSensitive: false), '')
        .replaceAll(RegExp(r'[^0-9Xx]'), '')
        .toUpperCase();

    if (_isValidIsbn10(compact) || _isValidIsbn13(compact)) {
      return compact;
    }
    return null;
  }

  static bool _isValidIsbn10(String value) {
    if (!RegExp(r'^\d{9}[\dX]$').hasMatch(value)) {
      return false;
    }

    var sum = 0;
    for (var index = 0; index < 10; index++) {
      final digit = index == 9 && value[index] == 'X'
          ? 10
          : int.parse(value[index]);
      sum += digit * (10 - index);
    }
    return sum % 11 == 0;
  }

  static bool _isValidIsbn13(String value) {
    if (!RegExp(r'^97[89]\d{10}$').hasMatch(value)) {
      return false;
    }

    var sum = 0;
    for (var index = 0; index < 12; index++) {
      final digit = int.parse(value[index]);
      sum += digit * (index.isEven ? 1 : 3);
    }
    final expectedCheckDigit = (10 - (sum % 10)) % 10;
    return int.parse(value[12]) == expectedCheckDigit;
  }
}
