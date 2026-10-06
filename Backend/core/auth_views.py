from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from core.auth import audit_auth_event, clear_refresh_cookie, set_refresh_cookie
from core.auth_serializers import AccessResponseSerializer, AuthUserSerializer, CookieRefreshSerializer, EmptySerializer, LoginResponseSerializer, LoginSerializer, user_payload
from drf_spectacular.utils import OpenApiResponse, extend_schema

User = get_user_model()
GENERIC_CREDENTIAL_ERROR = {'detail': 'Credenciales inválidas.'}


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_login'

    @extend_schema(
        request=LoginSerializer,
        responses={200: LoginResponseSerializer, 401: OpenApiResponse(description='Credenciales inválidas.')},
        tags=['Autenticación'],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            if not isinstance(request.data, dict) or not request.data.get('username') or not request.data.get('password'):
                audit_auth_event('login_failed', request, request.data.get('username', '') if isinstance(request.data, dict) else '')
                from django.contrib.auth.signals import user_login_failed
                user_login_failed.send(sender=User, request=request._request, credentials={'username': request.data.get('username', '') if isinstance(request.data, dict) else ''})
            return Response(GENERIC_CREDENTIAL_ERROR, status=status.HTTP_401_UNAUTHORIZED)
        user = serializer.validated_data['user']
        user_logged_in.send(sender=User, request=request._request, user=user)
        response = Response({'user': user_payload(user)})
        # Authentication above validates credentials; issue a fresh pair for this login.
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(user)
        response.data['access'] = str(token.access_token)
        set_refresh_cookie(response, str(token))
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_refresh'
    serializer_class = CookieRefreshSerializer

    @extend_schema(request=None, responses={200: AccessResponseSerializer, 401: OpenApiResponse(description='Sesión inválida.')}, tags=['Autenticación'])
    def post(self, request):
        raw_cookie = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if not raw_cookie:
            response = Response({'detail': 'Sesión inválida.'}, status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response
        serializer = CookieRefreshSerializer(data={'refresh': raw_cookie}, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except (ValidationError, InvalidToken, TokenError):
            response = Response({'detail': 'Sesión inválida.'}, status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response
        data = dict(serializer.validated_data)
        new_refresh = data.pop('refresh', None)
        response = Response({'access': data['access']})
        if new_refresh:
            set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    serializer_class = EmptySerializer

    @extend_schema(request=None, responses={204: OpenApiResponse(description='Sesión cerrada.')}, tags=['Autenticación'])
    def post(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if raw_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                RefreshToken(raw_token).blacklist()
            except (TokenError, InvalidToken):
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    @extend_schema(responses={200: AuthUserSerializer}, tags=['Autenticación'])
    def get(self, request):
        return Response(user_payload(request.user))


