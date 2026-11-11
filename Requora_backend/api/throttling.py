import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginIPRateThrottle(SimpleRateThrottle):
    scope = "auth_login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginAccountRateThrottle(SimpleRateThrottle):
    scope = "auth_login_account"

    def get_cache_key(self, request, view):
        identifier = request.data.get("username", "")
        if not isinstance(identifier, str) or not identifier.strip():
            return None
        normalized = identifier.strip().casefold().encode("utf-8")
        digest = hashlib.sha256(normalized).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


class RegistrationRateThrottle(SimpleRateThrottle):
    scope = "auth_registration"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
