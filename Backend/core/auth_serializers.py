from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from core.auth import audit_auth_event


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=False)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        request = self.context['request']
        user = authenticate(request=request, username=attrs['username'], password=attrs['password'])
        if user is None:
            audit_auth_event('login_failed', request, attrs['username'])
            raise ValidationError({'detail': 'Credenciales inválidas.'})
        audit_auth_event('login_success', request, user.get_username())
        update_last_login(None, user)
        attrs['user'] = user
        return attrs


class AuthUserSerializer(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=['ADMIN', 'CAJERO'])
    business = serializers.DictField(allow_null=True)
    permissions = serializers.DictField()


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = AuthUserSerializer()


class AccessResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class EmptySerializer(serializers.Serializer):
    pass


class CookieRefreshSerializer(TokenRefreshSerializer):
    """Accept refresh credentials exclusively from the httpOnly cookie."""

    def validate(self, attrs):
        raw_token = self.context['request'].COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if not raw_token:
            raise ValidationError({'detail': 'Sesión inválida.'})
        return super().validate({'refresh': raw_token})


def user_payload(user):
    role = 'ADMIN' if user.is_superuser else user.rol
    business = None
    if user.negocio_id:
        business = {'id': user.negocio_id, 'nombre': user.negocio.nombre}
    display_name = user.get_full_name().strip() or user.get_username()
    return {
        'id': str(user.pk),
        'username': user.get_username(),
        'name': display_name,
        'role': role,
        'business': business,
        'permissions': {
            'canViewFinancialReports': role == 'ADMIN',
            'canManageUsers': role == 'ADMIN',
            'canManageSettings': role == 'ADMIN',
        },
    }


