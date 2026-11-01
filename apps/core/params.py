"""Lectura única, tipada y normalizada de parámetros GET (plan §3.7 y §4).

Reglas implementadas:

* nombres case-insensitive y coincidencia exacta (``R-01``/``R-02``);
* alias heredados con seguimiento para la cabecera ``Deprecation``;
* detección de duplicados salvo parámetros multivaluados (``R-03``);
* valores vacíos opcionales = ausentes (``R-05``);
* límites de URL, número de parámetros y longitud de valor (``R-10``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from urllib.parse import parse_qsl

from . import validators
from .bbox import Bbox, parse_bbox
from .crs import CRS84, Crs, parse_crs
from .limits import Limits, load_limits
from .problems import BadRequest, InvalidParam, InvalidParameter, UriTooLong, invalid_parameter
from .temporal import DatetimeInterval, parse_datetime_interval

ALIASES: dict[str, str] = {
    "srs": "crs",
    "projection": "crs",
    "maxextent": "max-extent",
    "zoomconstrains": "zoom-constraints",
    "extentconstrains": "extent-constraints",
    "viewextent": "view-extent",
    "bgcolorcontainer": "bgcolor",
    "getfeatureinfo": "info-format",
    "wmcfile": "wmc",
    "implementation": "impl",
    "formato": "f",
    "typename": "typenames",
    "maxfeatures": "count",
    "cql_filter": "filter",
}

MULTIVALUED: frozenset[str] = frozenset({"layer", "collection", "property"})

SECRET_PARAMS: frozenset[str] = frozenset({"token", "ticket", "password", "authorization"})


class Parametros:
    """Vista inmutable y tipada de la query string."""

    def __init__(
        self,
        values: Mapping[str, Sequence[str]],
        *,
        names: Mapping[str, str] | None = None,
        limits: Limits | None = None,
        aliases: Mapping[str, str] | None = None,
        multivalued: frozenset[str] = MULTIVALUED,
    ) -> None:
        self._values: dict[str, list[str]] = {key: list(value) for key, value in values.items()}
        self._names: dict[str, str] = dict(names or {})
        self._limits = limits or load_limits()
        self._aliases = dict(aliases if aliases is not None else ALIASES)
        self._multivalued = multivalued
        self.deprecations: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    @classmethod
    def desde_query_string(
        cls,
        query_string: str,
        *,
        limits: Limits | None = None,
        nombre: str = "query string",
    ) -> Parametros:
        lim = limits or load_limits()
        if len(query_string) > lim.max_url_length:
            raise UriTooLong(
                f"La {nombre} supera el límite de {lim.max_url_length} caracteres.",
                headers={"Content-Length": "0"},
            )

        try:
            pairs = parse_qsl(
                query_string,
                keep_blank_values=True,
                strict_parsing=False,
                encoding="utf-8",
                errors="strict",
                max_num_fields=lim.max_params,
            )
        except ValueError as exc:
            if "Max number of fields" in str(exc):
                raise BadRequest(
                    f"La petición supera el máximo de {lim.max_params} parámetros."
                ) from exc
            raise InvalidParameter(
                "La query string no está correctamente codificada (RFC 3986).",
                invalid_params=[InvalidParam(nombre, "percent-encoding no válido")],
            ) from exc
        except UnicodeDecodeError as exc:
            raise InvalidParameter(
                "La query string no está correctamente codificada (RFC 3986).",
                invalid_params=[InvalidParam(nombre, "percent-encoding no válido")],
            ) from exc

        if len(pairs) > lim.max_params:
            raise BadRequest(
                f"La petición incluye {len(pairs)} parámetros y el máximo es {lim.max_params}.",
                invalid_params=[InvalidParam(nombre, "demasiados parámetros", len(pairs))],
            )

        values: dict[str, list[str]] = {}
        names: dict[str, str] = {}
        deprecations: list[tuple[str, str]] = []

        for raw_key, raw_value in pairs:
            key = raw_key.strip().lower()
            if not key:
                raise invalid_parameter("", "nombre de parámetro vacío", raw_key)

            canonical = ALIASES.get(key, key)
            if canonical != key:
                deprecations.append((raw_key, canonical))

            if len(raw_value) > lim.max_value_length:
                raise invalid_parameter(
                    canonical,
                    f"el valor supera {lim.max_value_length} caracteres",
                    raw_value[:64] + "...",
                )

            if canonical in values and canonical not in MULTIVALUED:
                raise InvalidParameter(
                    f"El parámetro «{canonical}» está repetido; solo se admite una vez.",
                    invalid_params=[
                        InvalidParam(canonical, "parámetro repetido", raw_key),
                    ],
                )

            values.setdefault(canonical, []).append(raw_value)
            names.setdefault(canonical, raw_key)

        instance = cls(values, names=names, limits=lim)
        instance.deprecations = deprecations
        return instance

    @classmethod
    def desde_request(cls, request, *, limits: Limits | None = None) -> Parametros:
        query_string = request.META.get("QUERY_STRING", "") or ""
        lim = limits or load_limits()
        full_path = request.META.get("PATH_INFO", "") + "?" + query_string
        if len(full_path) > lim.max_url_length:
            raise UriTooLong(
                f"La URL supera el límite de {lim.max_url_length} caracteres.",
            )
        return cls.desde_query_string(query_string, limits=lim)

    # ------------------------------------------------------------------
    # Inspección
    # ------------------------------------------------------------------
    @property
    def crudo(self) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType({key: tuple(value) for key, value in self._values.items()})

    @property
    def limites(self) -> Limits:
        return self._limits

    def __contains__(self, name: str) -> bool:
        return self._single(name) is not None

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"Parametros({self.a_dict()!r})"

    def tiene(self, name: str) -> bool:
        return name in self

    def nombre_original(self, name: str) -> str | None:
        return self._names.get(name)

    def claves(self) -> list[str]:
        return sorted(self._values)

    def desconocidos(self, permitidos: Sequence[str]) -> list[str]:
        allowed = {item.lower() for item in permitidos}
        return sorted(key for key in self._values if key not in allowed)

    def rechazar_desconocidos(self, permitidos: Sequence[str]) -> None:
        unknown = self.desconocidos(permitidos)
        if not unknown:
            return
        raise InvalidParameter(
            "La petición incluye parámetros no admitidos: " + ", ".join(unknown) + ".",
            invalid_params=[InvalidParam(name, "parámetro no admitido") for name in unknown],
        )

    def a_dict(self, *, ocultar_secretos: bool = True) -> dict[str, list[str]]:
        data: dict[str, list[str]] = {}
        for key, values in self._values.items():
            if ocultar_secretos and key.lower() in SECRET_PARAMS:
                data[key] = ["***"]
            else:
                data[key] = list(values)
        return data

    # ------------------------------------------------------------------
    # Accesores tipados
    # ------------------------------------------------------------------
    def texto(
        self,
        name: str,
        *,
        obligatorio: bool = False,
        defecto: str | None = None,
        max_len: int | None = None,
        recortar: bool = True,
    ) -> str | None:
        value = self._single(name)
        if value is None:
            if obligatorio:
                raise invalid_parameter(name, "es obligatorio y no se ha indicado")
            return defecto

        limit = max_len if max_len is not None else self._limits.max_value_length
        if len(value) > limit:
            raise invalid_parameter(name, f"supera el máximo de {limit} caracteres", value[:64])
        if recortar:
            value = value.strip()
        if not value:
            if obligatorio:
                raise invalid_parameter(name, "no puede estar vacío")
            return defecto
        return value

    def entero(
        self,
        name: str,
        *,
        obligatorio: bool = False,
        defecto: int | None = None,
        minimo: int | None = None,
        maximo: int | None = None,
    ) -> int | None:
        value = self.texto(name, obligatorio=obligatorio)
        if value is None:
            return defecto
        return validators.parse_int(value, name=name, minimum=minimo, maximum=maximo)

    def decimal(
        self,
        name: str,
        *,
        obligatorio: bool = False,
        defecto: float | None = None,
    ) -> float | None:
        value = self.texto(name, obligatorio=obligatorio)
        if value is None:
            return defecto
        return validators.parse_decimal(value, name=name)

    def booleano(
        self,
        name: str,
        *,
        obligatorio: bool = False,
        defecto: bool = False,
        legacy: bool = False,
    ) -> bool:
        value = self.texto(name, obligatorio=obligatorio)
        if value is None:
            return defecto
        return validators.parse_bool(value, name=name, legacy=legacy)

    def lista(
        self,
        name: str,
        *,
        defecto: Sequence[str] | None = None,
        separador: str = ",",
        max_items: int | None = None,
        max_item_length: int | None = None,
    ) -> list[str]:
        raws = self._values.get(name) or []
        items: list[str] = []
        for raw in raws:
            if raw == "":
                continue
            items.extend(
                validators.parse_list(
                    raw,
                    name=name,
                    separator=separador,
                    max_item_length=max_item_length,
                )
            )
        if not items:
            return list(defecto or [])
        if max_items is not None and len(items) > max_items:
            raise invalid_parameter(name, f"no se admiten más de {max_items} elementos", len(items))
        return items

    def enum(
        self,
        name: str,
        valores: Sequence[str],
        *,
        obligatorio: bool = False,
        defecto: str | None = None,
        casefold: bool = True,
    ) -> str | None:
        value = self.texto(name, obligatorio=obligatorio)
        if value is None:
            return defecto
        return validators.parse_enum(value, valores, name=name, casefold=casefold)

    def crs(
        self,
        name: str = "crs",
        *,
        defecto: Crs | None = CRS84,
        permitir_srid: bool = False,
    ) -> Crs | None:
        value = self.texto(name)
        if value is None:
            return defecto
        return parse_crs(value, name=name, allow_srid=permitir_srid)

    def bbox(
        self,
        name: str = "bbox",
        *,
        crs: Crs = CRS84,
        dimensiones: tuple[int, ...] = (4, 6),
        comprobar_dominio: bool = True,
    ) -> Bbox | None:
        value = self.texto(name)
        if value is None:
            return None
        return parse_bbox(
            value,
            crs=crs,
            name=name,
            dimensions=dimensiones,
            check_domain=comprobar_dominio,
        )

    def fecha_hora(
        self,
        name: str = "datetime",
        *,
        obligatorio: bool = False,
    ) -> DatetimeInterval | None:
        value = self.texto(name, obligatorio=obligatorio)
        if value is None:
            return None
        return parse_datetime_interval(value, name=name)

    def color(self, name: str = "bgcolor", *, defecto: str | None = None) -> str | None:
        value = self.texto(name)
        if value is None:
            return defecto
        return validators.parse_color(value, name=name)

    def callback(self) -> str | None:
        value = self.texto("callback")
        if value is None:
            return None
        return validators.validate_callback(value)

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------
    def _single(self, name: str) -> str | None:
        values = self._values.get(name)
        if not values:
            return None
        non_empty = [value for value in values if value != ""]
        if not non_empty:
            return None
        return non_empty[0]

    def __getitem__(self, name: str) -> tuple[str, ...]:
        return tuple(self._values.get(name, ()))


__all__ = ["ALIASES", "MULTIVALUED", "Parametros"]
