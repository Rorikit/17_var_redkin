import re
import json
from typing import Dict, List, Union, Optional, Any
from dataclasses import dataclass


@dataclass
class ConfigValue:
    pass


@dataclass
class NumberValue(ConfigValue):
    value: float


@dataclass
class StringValue(ConfigValue):
    value: str
    has_vars: bool = False


@dataclass
class ListValue(ConfigValue):
    values: List['ConfigValue']


@dataclass
class TableValue(ConfigValue):
    items: Dict[str, 'ConfigValue']

@dataclass
class VarRefValue(ConfigValue):
    name: str

class ConfigParser:
    def __init__(self):
        self.variables: Dict[str, ConfigValue] = {}
        self.pos = 0
        self.tokens = []
        self.current_line = 1

    def tokenize(self, text: str) -> List[tuple]:
        """Разбиваем текст на токены строго по спецификации"""
        tokens = []
        i = 0
        n = len(text)

        while i < n:
            # Пропускаем пробелы
            if text[i].isspace():
                if text[i] == '\n':
                    self.current_line += 1
                i += 1
                continue

            # Однострочные комментарии
            if text[i:i + 2] == '::':
                i = text.find('\n', i)
                if i == -1:
                    break
                continue

            # Многострочные комментарии
            if text[i:i + 3] == '{{!':
                i = text.find('!}}', i)
                if i == -1:
                    break
                i += 3
                continue

            # Числа (строго с точкой)
            num_match = re.match(r'[+-]?\d+\.\d+', text[i:])
            if num_match:
                tokens.append(('NUMBER', float(num_match.group()), self.current_line))
                i += len(num_match.group())
                continue

            # Строки
            if text[i:i + 2] == '@"':
                end = text.find('"', i + 2)
                if end == -1:
                    raise SyntaxError(f'Незакрытая строка на строке {self.current_line}')
                str_value = text[i + 2:end]
                tokens.append(('STRING', str_value, self.current_line))
                i = end + 1
                continue

            # Идентификаторы и ключевые слова
            id_match = re.match(r'[a-zA-Z][_a-zA-Z0-9]*', text[i:])
            if id_match:
                token_value = id_match.group()
                token_type = token_value.upper() if token_value in ['var', 'list', 'table'] else 'ID'
                tokens.append((token_type, token_value, self.current_line))
                i += len(token_value)
                continue

            # Символы
            char = text[i]
            if char in '()[],=$;':  # Добавили ;
                tokens.append((char, char, self.current_line))
                i += 1
                continue

            # Неизвестный символ - ошибка
            raise SyntaxError(f'Неизвестный символ "{text[i]}" на строке {self.current_line}')

        return tokens

    def parse(self, text: str) -> Dict[str, Any]:
        """Парсим конфигурацию"""
        self.tokens = self.tokenize(text)
        self.pos = 0

        while self.pos < len(self.tokens):
            token_type, token_value, line = self.tokens[self.pos]

            if token_type == 'VAR':
                self.parse_var_declaration()
            else:
                self.pos += 1

        # Обрабатываем подстановку переменных
        self.process_variable_substitution()

        # Конвертируем в обычные Python типы
        return self.convert_variables()

    def parse_var_declaration(self):
        """Парсим объявление переменной (с обязательной ;)"""
        # Пропускаем 'var'
        self.pos += 1

        # Получаем имя переменной
        if self.pos >= len(self.tokens) or self.tokens[self.pos][0] != 'ID':
            raise SyntaxError(f'Ожидалось имя переменной на строке {self.tokens[self.pos - 1][2]}')

        var_name = self.tokens[self.pos][1]
        self.pos += 1

        # Пропускаем '='
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != '=':
            raise SyntaxError(f'Ожидалось "=" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        # Парсим значение
        value = self.parse_value()

        # Сохраняем переменную
        self.variables[var_name] = value

        # Точка с запятой обязательна
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != ';':
            raise SyntaxError(f'Ожидалось ";" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

    def parse_value(self):
        """Парсим значение"""
        if self.pos >= len(self.tokens):
            raise SyntaxError(f'Ожидалось значение')

        token_type, token_value, line = self.tokens[self.pos]

        if token_type == 'NUMBER':
            self.pos += 1
            return NumberValue(token_value)

        elif token_type == 'STRING':
            self.pos += 1
            has_vars = '$' in token_value
            return StringValue(token_value, has_vars)

        elif token_type == 'LIST':
            return self.parse_list()

        elif token_type == 'TABLE':
            return self.parse_table()

        elif token_type == '$':
            return self.parse_var_reference()

        else:
            raise SyntaxError(f'Неожиданный токен {token_value} на строке {line}')

    def parse_list(self):
        """Парсим список"""
        # Пропускаем 'list'
        self.pos += 1

        # Пропускаем '('
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != '(':
            raise SyntaxError(f'Ожидалось "(" после list на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        values = []

        # Пустой список
        if self.pos < len(self.tokens) and self.tokens[self.pos][1] == ')':
            self.pos += 1
            return ListValue(values)

        while self.pos < len(self.tokens) and self.tokens[self.pos][1] != ')':
            value = self.parse_value()
            values.append(value)

            if self.pos < len(self.tokens) and self.tokens[self.pos][1] == ',':
                self.pos += 1
            elif self.pos < len(self.tokens) and self.tokens[self.pos][1] != ')':
                raise SyntaxError(f'Ожидалось "," или ")" на строке {self.tokens[self.pos][2]}')

        # Пропускаем ')'
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != ')':
            raise SyntaxError(f'Ожидалось ")" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        return ListValue(values)

    def parse_table(self):
        """Парсим таблицу"""
        # Пропускаем 'table'
        self.pos += 1

        # Пропускаем '('
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != '(':
            raise SyntaxError(f'Ожидалось "(" после table на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        # Пропускаем '['
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != '[':
            raise SyntaxError(f'Ожидалось "[" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        items = {}

        # Пустая таблица
        if self.pos < len(self.tokens) and self.tokens[self.pos][1] == ']':
            self.pos += 1
            self.pos += 1  # Пропускаем ')'
            return TableValue(items)

        while self.pos < len(self.tokens) and self.tokens[self.pos][1] != ']':
            # Получаем имя ключа
            if self.pos >= len(self.tokens) or self.tokens[self.pos][0] != 'ID':
                raise SyntaxError(f'Ожидалось имя ключа на строке {self.tokens[self.pos - 1][2]}')

            key = self.tokens[self.pos][1]
            self.pos += 1

            # Пропускаем '='
            if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != '=':
                raise SyntaxError(f'Ожидалось "=" после {key} на строке {self.tokens[self.pos - 1][2]}')
            self.pos += 1

            # Получаем значение
            value = self.parse_value()
            items[key] = value

            # Пропускаем ',' если есть
            if self.pos < len(self.tokens) and self.tokens[self.pos][1] == ',':
                self.pos += 1
            elif self.pos < len(self.tokens) and self.tokens[self.pos][1] != ']':
                raise SyntaxError(f'Ожидалось "," или "]" на строке {self.tokens[self.pos][2]}')

        # Пропускаем ']'
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != ']':
            raise SyntaxError(f'Ожидалось "]" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        # Пропускаем ')'
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != ')':
            raise SyntaxError(f'Ожидалось ")" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        return TableValue(items)

    def parse_var_reference(self):
        """Парсим ссылку на переменную (только простые имена $var$)"""
        # Пропускаем первый '$'
        self.pos += 1

        # Получаем имя переменной
        if self.pos >= len(self.tokens) or self.tokens[self.pos][0] != 'ID':
            raise SyntaxError(f'Ожидалось имя переменной после $ на строке {self.tokens[self.pos - 1][2]}')

        var_name = self.tokens[self.pos][1]
        self.pos += 1

        # Проверяем, нет ли точки после имени (недопустимо)
        if self.pos < len(self.tokens) and self.tokens[self.pos][1] == '.':
            raise SyntaxError(f'Вложенные ссылки $var.prop$ не поддерживаются на строке {self.tokens[self.pos][2]}')

        # Пропускаем второй '$'
        if self.pos >= len(self.tokens) or self.tokens[self.pos][1] != '$':
            raise SyntaxError(f'Ожидалось "$" на строке {self.tokens[self.pos - 1][2]}')
        self.pos += 1

        # Возвращаем специальное значение для подстановки
        # ВАЖНО: не StringValue, а VarRefValue!
        return VarRefValue(var_name)

    def process_variable_substitution(self):
        """Обрабатываем подстановку переменных во всех значениях"""
        for var_name, value in self.variables.items():
            self.variables[var_name] = self.substitute_vars_in_value(value)

    def substitute_vars_in_value(self, value: ConfigValue) -> ConfigValue:
        """Рекурсивно подставляем переменные в значение"""
        if isinstance(value, NumberValue):
            return value

        elif isinstance(value, StringValue):
            if value.has_vars:
                result = value.value
                # Ищем простые переменные $var$

                pattern = r'\$([^$\n]+?)\$'  # Ищем любые символы между $
                matches = re.findall(pattern, result)

                for var_name in matches:
                    # Проверяем, что имя не содержит точек
                    if '.' in var_name:
                        raise SyntaxError(
                            f'Вложенные ссылки ${var_name}$ не поддерживаются. Используйте только простые имена переменных.')

                    # Проверяем формат имени переменной
                    if not re.match(r'^[a-zA-Z][_a-zA-Z0-9]*$', var_name):
                        raise SyntaxError(f'Неверный формат имени переменной: ${var_name}$')

                    if var_name in self.variables:
                        str_value = self.get_string_value(self.variables[var_name])
                        result = result.replace(f'${var_name}$', str_value)
                    else:
                        raise NameError(f'Неопределенная переменная ${var_name}$')

                return StringValue(result, False)
            return value

        elif isinstance(value, VarRefValue):
            # Проверяем формат имени переменной
            if '.' in value.name:
                raise SyntaxError(
                    f'Вложенные ссылки ${value.name}$ не поддерживаются. Используйте только простые имена переменных.')

            if not re.match(r'^[a-zA-Z][_a-zA-Z0-9]*$', value.name):
                raise SyntaxError(f'Неверный формат имени переменной: ${value.name}$')

            # Заменяем ссылку на переменную на её значение
            if value.name in self.variables:
                return self.substitute_vars_in_value(self.variables[value.name])
            else:
                raise NameError(f'Неопределенная переменная ${value.name}$')

        elif isinstance(value, ListValue):
            new_values = [self.substitute_vars_in_value(v) for v in value.values]
            return ListValue(new_values)

        elif isinstance(value, TableValue):
            new_items = {k: self.substitute_vars_in_value(v) for k, v in value.items.items()}
            return TableValue(new_items)

        return value

    def get_string_value(self, value) -> str:
        """Получаем строковое представление значения"""
        if isinstance(value, NumberValue):
            return str(value.value)
        elif isinstance(value, StringValue):
            return value.value
        elif isinstance(value, VarRefValue):
            if value.name in self.variables:
                return self.get_string_value(self.variables[value.name])
            return f"${value.name}$"
        elif isinstance(value, ListValue):
            return str([self.get_string_value(v) for v in value.values])
        elif isinstance(value, TableValue):
            return str({k: self.get_string_value(v) for k, v in value.items.items()})
        return str(value)

    def convert_variables(self) -> Dict[str, Any]:
        """Конвертируем все переменные в обычные Python типы"""
        result = {}
        for name, value in self.variables.items():
            result[name] = self.convert_value(value)
        return result

    def convert_value(self, value: ConfigValue) -> Any:
        """Конвертируем ConfigValue в Python тип"""
        if isinstance(value, NumberValue):
            return value.value
        elif isinstance(value, StringValue):
            return value.value
        elif isinstance(value, ListValue):
            return [self.convert_value(v) for v in value.values]
        elif isinstance(value, TableValue):
            return {k: self.convert_value(v) for k, v in value.items.items()}
        return value


def parse_config_to_json(text: str) -> dict:
    """Упрощенная функция для парсинга конфигурации в JSON"""
    parser = ConfigParser()
    return parser.parse(text)