import unittest
import json
import tempfile
import os
from config_parser import parse_config_to_json


class TestConfigParser(unittest.TestCase):
    def test_numbers(self):
        config = "var pi = 3.14;"
        result = parse_config_to_json(config)
        self.assertEqual(result["pi"], 3.14)

    def test_negative_numbers(self):
        config = "var temp = -15.5;"
        result = parse_config_to_json(config)
        self.assertEqual(result["temp"], -15.5)

    def test_positive_numbers(self):
        config = "var temp = +25.5;"
        result = parse_config_to_json(config)
        self.assertEqual(result["temp"], 25.5)

    def test_strings(self):
        config = 'var message = @"Hello World";'
        result = parse_config_to_json(config)
        self.assertEqual(result["message"], "Hello World")

    def test_strings_with_unicode(self):
        config = 'var message = @"Привет, мир! 🌍";'
        result = parse_config_to_json(config)
        self.assertEqual(result["message"], "Привет, мир! 🌍")

    def test_empty_list(self):
        config = "var empty = list();"
        result = parse_config_to_json(config)
        self.assertEqual(result["empty"], [])

    def test_list_with_numbers(self):
        config = "var numbers = list(1.0, 2.0, 3.0);"
        result = parse_config_to_json(config)
        self.assertEqual(result["numbers"], [1.0, 2.0, 3.0])

    def test_list_with_strings(self):
        config = 'var colors = list(@"красный", @"зеленый", @"синий");'
        result = parse_config_to_json(config)
        self.assertEqual(result["colors"], ["красный", "зеленый", "синий"])

    def test_list_with_mixed_types(self):
        config = 'var mixed = list(1.0, @"два", 3.0);'
        result = parse_config_to_json(config)
        self.assertEqual(result["mixed"], [1.0, "два", 3.0])

    def test_empty_table(self):
        config = "var empty = table([]);"
        result = parse_config_to_json(config)
        self.assertEqual(result["empty"], {})

    def test_table_simple(self):
        config = 'var user = table([name = @"Иван", age = 25.0]);'
        result = parse_config_to_json(config)
        self.assertEqual(result["user"], {"name": "Иван", "age": 25.0})

    def test_table_complex(self):
        config = """
        var config = table([
            host = @"localhost",
            port = 8080.0,
            ssl = table([
                cert = @"/path/cert.pem"
            ])
        ]);
        """
        result = parse_config_to_json(config)
        expected = {
            "host": "localhost",
            "port": 8080.0,
            "ssl": {
                "cert": "/path/cert.pem"
            }
        }
        self.assertEqual(result["config"], expected)

    def test_var_reference_simple(self):
        config = """
        var name = @"Иван";
        var greeting = @"Привет, $name$!";
        """
        result = parse_config_to_json(config)
        self.assertEqual(result["greeting"], "Привет, Иван!")

    def test_var_reference_multiple(self):
        config = """
        var first = @"Hello";
        var second = @"World";
        var message = @"$first$ $second$!";
        """
        result = parse_config_to_json(config)
        self.assertEqual(result["message"], "Hello World!")

    def test_nested_list_in_table(self):
        config = """
        var server = table([
            hosts = list(@"localhost", @"127.0.0.1"),
            ports = list(80.0, 443.0)
        ]);
        """
        result = parse_config_to_json(config)
        expected = {
            "hosts": ["localhost", "127.0.0.1"],
            "ports": [80.0, 443.0]
        }
        self.assertEqual(result["server"], expected)

    def test_nested_table_in_list(self):
        config = """
        var users = list(
            table([name = @"Alice", age = 30.0]),
            table([name = @"Bob", age = 25.0])
        );
        """
        result = parse_config_to_json(config)
        expected = [
            {"name": "Alice", "age": 30.0},
            {"name": "Bob", "age": 25.0}
        ]
        self.assertEqual(result["users"], expected)

    def test_comments_single_line(self):
        config = """
        :: Это комментарий
        var value = 42.0;
        :: Ещё комментарий
        var name = @"test";
        """
        result = parse_config_to_json(config)
        self.assertEqual(result["value"], 42.0)
        self.assertEqual(result["name"], "test")

    def test_comments_multi_line(self):
        config = """
        var a = 1.0;
        {{!
            Это многострочный
            комментарий
        !}}
        var b = 2.0;
        """
        result = parse_config_to_json(config)
        self.assertEqual(result["a"], 1.0)
        self.assertEqual(result["b"], 2.0)

    def test_semicolon_required(self):
        """Тест обязательности точки с запятой"""
        config = "var x = 1.0"  # Нет ;
        with self.assertRaises(SyntaxError):
            parse_config_to_json(config)

    def test_number_format_strict(self):
        """Тест строгого формата чисел (обязательна точка)"""
        config = "var x = 10;"  # Нет точки
        with self.assertRaises(SyntaxError):
            parse_config_to_json(config)

    def test_var_reference_only_simple(self):
        """Тест что только простые имена $var$, а не $var.prop$"""
        config = """
        var server = table([port = 8080.0]);
        var msg = @"Порт: $server.port$";
        """
        # Проверяем что есть ошибка при парсинге
        try:
            parse_config_to_json(config)
            self.fail("Ожидалась ошибка SyntaxError или NameError")
        except (SyntaxError, NameError):
            # Ожидаемое поведение
            pass
        except Exception as e:
            self.fail(f"Неожиданная ошибка: {type(e).__name__}: {e}")

    def test_identifier_format(self):
        """Тест формата идентификаторов"""
        config = "var 123abc = 1.0;"  # Неверный идентификатор
        with self.assertRaises(SyntaxError):
            parse_config_to_json(config)

    def test_unknown_char_error(self):
        """Тест ошибки неизвестного символа"""
        config = "var x = 1.0 # комментарий;"
        with self.assertRaises(SyntaxError):
            parse_config_to_json(config)

    def test_file_parsing_simple(self):
        """Тест парсинга из файла"""
        content = """var app_name = @"Test App";\nvar version = 1.0;\nvar settings = table([mode = @"production"]);"""

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name

        try:
            # Парсим напрямую через нашу функцию
            with open(temp_file, 'r', encoding='utf-8') as f:
                file_content = f.read()

            result = parse_config_to_json(file_content)

            self.assertEqual(result["app_name"], "Test App")
            self.assertEqual(result["version"], 1.0)
            self.assertEqual(result["settings"], {"mode": "production"})
        finally:
            os.unlink(temp_file)

    def test_webserver_config(self):
        """Тест конфига веб-сервера"""
        # Читаем реальный файл из examples
        config_path = os.path.join('examples', 'webserver.config')

        # Проверяем что файл существует
        if not os.path.exists(config_path):
            self.skipTest(f"Файл {config_path} не найден")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        result = parse_config_to_json(config_content)

        # Проверяем ключевые поля
        self.assertEqual(result["server_name"], "MyWebServer")
        self.assertEqual(result["port"], 8080.0)
        self.assertEqual(result["max_connections"], 1000.0)
        self.assertEqual(result["timeout"], 30.0)

        # Проверяем список
        self.assertEqual(result["hosts"], ["localhost", "127.0.0.1", "example.com"])

        # Проверяем таблицы
        self.assertEqual(result["logging"]["level"], "debug")
        self.assertEqual(result["logging"]["path"], "/var/log/webserver")

        self.assertEqual(result["ssl"]["cert_path"], "/etc/ssl/cert.pem")
        self.assertEqual(result["ssl"]["key_path"], "/etc/ssl/key.pem")

        # Проверяем подстановку переменных в строках
        self.assertEqual(result["welcome_message"], "Добро пожаловать на MyWebServer!")
        self.assertEqual(result["server_info"], "Сервер работает на порту 8080.0 с таймаутом 30.0")

    def test_game_config(self):
        """Тест конфига игры"""
        # Читаем реальный файл из examples
        config_path = os.path.join('examples', 'game.config')

        # Проверяем что файл существует
        if not os.path.exists(config_path):
            self.skipTest(f"Файл {config_path} не найден")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        result = parse_config_to_json(config_content)

        # Проверяем ключевые поля
        self.assertEqual(result["game_title"], "Space Adventure")
        self.assertEqual(result["version"], 1.20)
        self.assertEqual(result["max_players"], 4.0)

        # Проверяем таблицы
        self.assertEqual(result["resolution"]["width"], 1920.0)
        self.assertEqual(result["resolution"]["height"], 1080.0)

        self.assertEqual(result["player"]["health"], 100.0)
        self.assertEqual(result["player"]["speed"], 5.0)
        self.assertEqual(result["player"]["inventory_size"], 50.0)

        # Проверяем списки
        self.assertEqual(result["difficulty_levels"], ["easy", "normal", "hard"])

        # Проверяем вложенные структуры
        self.assertEqual(len(result["enemies"]), 2)
        self.assertEqual(result["enemies"][0]["name"], "Alien Drone")
        self.assertEqual(result["enemies"][0]["health"], 50.0)
        self.assertEqual(result["enemies"][0]["damage"], 10.0)

        self.assertEqual(result["enemies"][1]["name"], "Space Pirate")
        self.assertEqual(result["enemies"][1]["health"], 100.0)
        self.assertEqual(result["enemies"][1]["damage"], 20.0)

        # Проверяем подстановку переменных
        self.assertEqual(result["game_info"], "Space Adventure версии 1.2")
        self.assertEqual(result["players_info"], "Максимальное количество игроков: 4.0")

    def test_undefined_variable_error(self):
        """Тест ошибки неопределенной переменной"""
        config = 'var msg = @"Привет, $undefined$";'
        with self.assertRaises(NameError):
            parse_config_to_json(config)

    def test_variable_in_list(self):
        """Тест переменной внутри списка"""
        config = """
        var name = @"World";
        var greetings = list(@"Hello", $name$, @"!");
        """
        result = parse_config_to_json(config)
        self.assertEqual(result["greetings"], ["Hello", "World", "!"])

    def test_variable_in_table_value(self):
        """Тест переменной в значении таблицы"""
        config = """
        var default_port = 8080.0;
        var server = table([
            name = @"MyServer",
            port = $default_port$
        ]);
        """
        result = parse_config_to_json(config)
        self.assertEqual(result["server"], {"name": "MyServer", "port": 8080.0})


if __name__ == '__main__':
    unittest.main()