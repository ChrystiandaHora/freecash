from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

from core.services.criar_usuario import criar_usuario_com_ecosistema


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        senha = request.POST.get("password")

        user = authenticate(request, username=username, password=senha)

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        messages.error(request, "Usuário ou senha inválidos.")
        return redirect("login")

    return render(request, "login.html")


def registrar_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        senha = request.POST.get("password")

        if not username or not senha:
            messages.error(request, "Preencha usuário e senha.")
            return redirect("registrar")

        usuario = criar_usuario_com_ecosistema(username, senha)
        login(request, usuario)

        messages.success(request, "Conta criada com sucesso.")
        return redirect("dashboard")

    return render(request, "registrar.html")
