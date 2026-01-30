from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

from core.services.criar_usuario import criar_usuario_com_ecosistema


class LadingPageView(View):
    template_name = "ladingPage.html"

    def get(self, request):
        # Apenas exibe a landing page
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm = request.POST.get("confirm")

        # ----- Detecta se é login ou registro -----
        is_register = bool(confirm)  # se confirm veio preenchido, é registro

        print(f"is_register: {is_register}")

        if not username or not password:
            messages.error(request, "Preencha usuário e senha.")
            return redirect("landing")

        # ------------------------------------------
        # REGISTRO DE NOVA CONTA
        # ------------------------------------------
        if is_register:
            if not confirm:
                messages.error(request, "Confirme sua senha.")
                return redirect("landing")

            if password != confirm:
                messages.error(request, "As senhas não coincidem.")
                return redirect("landing")

            if User.objects.filter(username=username).exists():
                messages.error(request, "Esse nome de usuário já está em uso.")
                return redirect("landing")

            # Cria usuário + estrutura interna
            usuario = criar_usuario_com_ecosistema(username, password)

            # Efetua login automático
            login(request, usuario)

            messages.success(request, "Conta criada com sucesso!")
            return redirect("dashboard")

        # ------------------------------------------
        # LOGIN NORMAL
        # ------------------------------------------
        user = authenticate(request, username=username, password=password)
        print(f"Usuário autenticado: {user}")

        if user is None:
            messages.error(request, "Usuário ou senha incorretos.")
            return redirect("landing")

        print(f"Usuário {username} autenticado com sucesso.")
        login(request, user)
        return redirect("dashboard")
