# System Patterns *Optional*

This file documents recurring patterns and standards used in the project.
It is optional, but recommended to be updated as the project evolves.
2025-04-04 18:25:00 - Log of updates made.

*

## Coding Patterns

* **Все комментарии в коде должны быть написаны исключительно на английском языке.**

* **Модульная архитектура**
  - Использование Django приложений для разделения функциональности
  - Четкое разделение ответственности между приложениями
  - Повторное использование компонентов между разными сайтами

* **Слоистая архитектура**
  - Models: определение структуры данных и бизнес-логики
  - Views: обработка HTTP-запросов и формирование ответов
  - Services: инкапсуляция бизнес-логики и операций
  - Selectors: извлечение данных из базы данных
  - Forms: валидация входных данных
  - Serializers: преобразование данных для API
  - Resources: импорт/экспорт данных (django-import-export)

* **Контроль доступа**
  - Использование permissions для детального контроля доступа
  - Ролевая модель для разграничения прав пользователей
  - Middleware для проверки аутентификации и авторизации
  - Миксины для ограничения доступа к представлениям (например, CuratorOnlyMixin)

* **Обработка событий**
  - Использование Django signals для слабосвязанной коммуникации между компонентами
  - Асинхронная обработка событий через Celery

* **Шаблонизация**
  - Использование Jinja2 для шаблонов
  - Разделение логики и представления
  - Использование включаемых шаблонов для повторного использования кода (например, _results_tab.html)

* **Паттерн Mixin**
  - Использование миксинов для добавления функциональности к классам
  - Примеры: CuratorOnlyMixin, ApplicantRandomizeContestMixin
  - Позволяет избежать дублирования кода и улучшает его поддерживаемость

* **Паттерн Factory Method**
  - Использование фабричных методов для создания объектов
  - Пример: методы get_testing_record(), get_exam_record(), get_olympiad_record() в модели Applicant
  - Инкапсулирует логику создания объектов и делает код более гибким

## Architectural Patterns

* **Многосайтовая архитектура**
  - Общий код в директории lms/
  - Специфичный код для каждого сайта в отдельных директориях
  - Использование Django Sites Framework для разделения контента

* **Интеграция с внешними сервисами**
  - Yandex.Contest: проверка заданий по программированию и проведение олимпиад
  - Gerrit: система код-ревью
  - Yandex.Disk: хранение файлов
  - Yandex.Passport: аутентификация пользователей
  - LDAP: интеграция с корпоративными системами

* **Кэширование и очереди**
  - Redis для кэширования данных и управления очередями
  - Celery для асинхронной обработки задач
  - Планировщик задач для периодических операций

* **API-ориентированная архитектура**
  - REST API для взаимодействия с фронтендом
  - Документация API через Swagger/OpenAPI
  - Версионирование API

* **Масштабируемость**
  - Контейнеризация с использованием Docker
  - Оркестрация через Kubernetes
  - Горизонтальное масштабирование компонентов

* **Паттерн Context Provider**
  - Использование функций для подготовки контекста для шаблонов
  - Пример: get_applicant_context() для подготовки данных для страницы деталей абитуриента
  - Позволяет повторно использовать логику подготовки данных в разных представлениях

* **Паттерн Service Layer**
  - Выделение бизнес-логики в отдельные сервисные функции и классы
  - Пример: YandexContestAPI для взаимодействия с Yandex.Contest
  - Улучшает тестируемость и поддерживаемость кода

## Testing Patterns

* **Фреймворк тестирования**
  - Использование pytest для модульных и интеграционных тестов
  - Отдельные директории tests/ в каждом приложении
  - Конфигурация тестов через pytest.ini

* **Организация тестовых данных**
  - Использование фикстур для подготовки тестовых данных
  - Factory Boy для генерации тестовых объектов
  - Моки и стабы для изоляции компонентов

* **Типы тестов**
  - Модульные тесты для отдельных компонентов
  - Интеграционные тесты для проверки взаимодействия компонентов
  - Функциональные тесты для проверки пользовательских сценариев
  - API-тесты для проверки REST API

* **CI/CD**
  - Автоматическое выполнение тестов при коммитах
  - Проверка покрытия кода тестами
  - Линтеры для проверки качества кода

## Паттерны моделирования данных

* **Наследование моделей**
  - Использование абстрактных базовых классов для общей функциональности
  - Наследование от базовых моделей для специализированных случаев
  - Пример: `Olympiad` наследуется от `TimeStampedModel` и использует миксины `YandexContestIntegration` и `ApplicantRandomizeContestMixin`

* **Композиция моделей**
  - Связывание моделей через ForeignKey и ManyToMany отношения
  - Использование промежуточных моделей для сложных отношений
  - Пример: `Olympiad` связан с `Applicant` и `Location` через ForeignKey

* **Расширение функциональности**
  - Добавление методов в модели для инкапсуляции бизнес-логики
  - Пример: методы `total_score` и `total_score_display()` в модели `Olympiad` для расчета и форматирования суммы баллов

* **Паттерн Annotation**
  - Использование аннотаций Django ORM для оптимизации запросов
  - Пример: аннотация `olympiad__total_score_coalesce` в методе `get_queryset()` класса `ApplicantListView`
  - Позволяет выполнять вычисления на уровне базы данных, а не в Python-коде
