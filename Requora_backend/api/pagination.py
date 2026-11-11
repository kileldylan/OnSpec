from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class OptionalPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    max_limit = 100

    def get_page_size(self, request):
        if request.query_params.get(self.page_size_query_param) is not None:
            return super().get_page_size(request)
        limit = request.query_params.get("limit")
        if limit is None:
            return None
        try:
            return min(max(int(limit), 1), self.max_limit)
        except (TypeError, ValueError):
            return self.page_size


class OptionalPaginationMixin:
    pagination_class = OptionalPageNumberPagination

    def paginate_queryset(self, queryset):
        if not any(
            name in self.request.query_params
            for name in ("page", "page_size", "limit")
        ):
            return None
        return super().paginate_queryset(queryset)

    def list_response(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset
        serializer = serializer_class(
            items,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
