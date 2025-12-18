#!/usr/bin/env python3
import sys
import json
import argparse
from config_parser import parse_config_to_json


def main():
    parser = argparse.ArgumentParser(
        description='Конвертер учебного конфигурационного языка в JSON',
        epilog='Пример: python main.py -i config.config'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Путь к входному файлу (обязательно)'
    )

    args = parser.parse_args()

    try:
        # Чтение входного файла
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()

        # Парсинг конфигурации
        json_data = parse_config_to_json(content)

        # Вывод в стандартный вывод
        json.dump(json_data, sys.stdout, ensure_ascii=False, indent=2)
        print()  # Добавляем перенос строки в конце

    except FileNotFoundError:
        print(f"Ошибка: Файл '{args.input}' не найден", file=sys.stderr)
        sys.exit(1)
    except SyntaxError as e:
        print(f"Синтаксическая ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except NameError as e:
        print(f"Ошибка переменной: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неизвестная ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()