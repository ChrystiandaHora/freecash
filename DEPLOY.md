# Deploy em VPS

Guia do primeiro deploy do FreeCash num servidor real, escrito para quem nunca
publicou uma aplicação. Cada passo diz **o que** fazer e **por que** — porque a
maior parte dos problemas de deploy vem de um passo executado sem entender o que
ele protege.

Ao final você terá: a aplicação rodando em contêineres, banco com volume
persistente, reinício automático se algo cair e um caminho claro para ligar HTTPS
quando quiser.

**Ordem recomendada:** faça uma vez o [ensaio local](#ensaio-antes-de-ir-para-o-vps)
antes de contratar servidor. Errar no seu computador é grátis.

---

## O que você precisa contratar

Uma **VPS** é um computador alugado, ligado o tempo todo, ao qual você acessa por
linha de comando.

| Item | Recomendação | Por quê |
|---|---|---|
| Sistema | Ubuntu 24.04 LTS | É o que a maioria da documentação assume. LTS tem suporte longo. |
| Memória | **2 GB** no mínimo | O build do frontend (Vite) é o passo mais pesado. Com 1 GB ele costuma ser morto pelo sistema no meio. |
| Disco | 20 GB | Imagens Docker ocupam alguns GB. |
| Provedores | Hetzner, DigitalOcean, Vultr, Contabo | Faixa de US$ 5–7/mês nesse porte. |

Não precisa de domínio para começar: dá para acessar pelo IP. Nem de Kubernetes —
para uma aplicação com um banco, Docker Compose é a ferramenta certa, e
acrescentar orquestração aqui só adiciona peças para manter.

---

## Passo 1 — Chave SSH

O acesso ao servidor é por **par de chaves**, não por senha. São dois arquivos:

- **privada** (`~/.ssh/freecash_vps`) — fica na sua máquina, **nunca** sai dela;
- **pública** (`~/.ssh/freecash_vps.pub`) — você entrega ao servidor.

O servidor usa a pública para propor um desafio que só a privada resolve. Isso
elimina a força bruta de senha, que é o ataque que todo servidor com porta 22
aberta recebe continuamente, desde o primeiro minuto de vida.

Na **sua** máquina:

```bash
ssh-keygen -t ed25519 -C "freecash-vps" -f ~/.ssh/freecash_vps
cat ~/.ssh/freecash_vps.pub          # copie a linha inteira
```

A frase secreta (passphrase) pedida é opcional e protege a chave caso seu
computador seja acessado por outra pessoa.

Cole a chave pública no painel do provedor, no campo "SSH Key", **ao criar** a
máquina. Depois disso:

```bash
ssh -i ~/.ssh/freecash_vps root@SEU_IP
```

Para não repetir o `-i` toda vez, adicione ao seu `~/.ssh/config`:

```
Host freecash
    HostName SEU_IP
    User deploy
    IdentityFile ~/.ssh/freecash_vps
```

E o acesso passa a ser `ssh freecash`.

---

## Passo 2 — Preparar o servidor

Tudo abaixo roda **dentro** do servidor, conectado como `root`.

### 2.1 Atualizar e criar um usuário comum

Operar como `root` significa que qualquer comando errado é irreversível e que
qualquer processo comprometido tem o sistema inteiro.

```bash
apt update && apt upgrade -y
adduser deploy                      # define uma senha quando pedir
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # copia sua chave
```

Antes de fechar esta sessão, **abra outro terminal** e confirme que
`ssh -i ~/.ssh/freecash_vps deploy@SEU_IP` funciona. Se você desabilitar o login
de root sem testar isso, fica trancado para fora do próprio servidor.

### 2.2 Fechar o acesso por senha

```bash
sudo nano /etc/ssh/sshd_config
```

Garanta estas três linhas:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart ssh
```

### 2.3 Firewall

Fecha tudo e reabre só o necessário. Sem isso, o Postgres em contêiner pode
acabar exposto à internet por uma publicação de porta descuidada.

```bash
sudo ufw allow OpenSSH      # 22 — se esquecer esta linha, você se tranca fora
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 2.4 Atualizações de segurança automáticas

```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### 2.5 Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
```

Saia e entre de novo (`exit`, depois `ssh` outra vez) para o grupo valer. Teste:

```bash
docker run --rm hello-world
docker compose version
```

---

## Passo 3 — Código e configuração

```bash
cd ~
git clone https://github.com/ChrystiandaHora/freecash.git
cd freecash
cp .env_example .env
```

Gere uma chave secreta de verdade — a do exemplo é pública e serve para assinar
os tokens de sessão de todo mundo:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Edite o `.env` (`nano .env`). O mínimo para subir por IP, sem HTTPS:

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<a chave gerada acima>
DJANGO_ALLOWED_HOSTS=SEU_IP

DB_NAME=freecash_db
DB_USER=freecash_user
DB_PASS=<uma senha longa e aleatória, diferente da chave secreta>
DB_HOST=postgres
DB_PORT=5432

VITE_API_URL=http://SEU_IP
DJANGO_CSRF_TRUSTED_ORIGINS=http://SEU_IP
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_AUTH_COOKIE_SECURE=False
DJANGO_SECURE_HSTS_SECONDS=0

HTTP_PORT=80
GUNICORN_WORKERS=3
```

E-mail: sem `EMAIL_HOST` configurado, o cadastro funciona mas ninguém recebe o
link de verificação. A carência de alguns dias deixa a conta utilizável até lá —
mas redefinir senha fica indisponível. Configure um SMTP quando for usar de
verdade.

> **Por que o `.env` decide tanta coisa:** o `settings.py` roda
> `validar_config_producao()` no boot e **recusa iniciar** com `DEBUG=False` se a
> chave ainda for a de exemplo, se faltar credencial de banco ou se
> `ALLOWED_HOSTS` estiver vazia. Se o contêiner do backend morrer logo ao subir,
> leia o log: a mensagem diz exatamente qual variável falta. É proteção, não bug.

---

## Passo 4 — Subir

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

A primeira execução leva alguns minutos (baixa imagens, compila dependências,
faz o build do frontend). O que acontece nela:

1. Postgres sobe e só é considerado pronto quando responde ao `pg_isready`.
2. O backend espera esse sinal, então o `entrypoint.sh` aplica as migrations e
   cria a tabela de cache do throttle.
3. O gunicorn assume, com o número de workers do `.env`.
4. O nginx serve o SPA já compilado e faz proxy de `/api/` para o backend.

Conferir:

```bash
docker compose -f docker-compose.prod.yml ps        # todos "healthy"
curl http://localhost/api/health/                   # {"status": "ok"}
docker compose -f docker-compose.prod.yml logs -f backend
```

Crie seu usuário administrador:

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Acesse `http://SEU_IP` no navegador.

---

## Passo 5 — HTTPS: três caminhos

Enquanto estiver em HTTP puro, o cookie de sessão e a senha trafegam legíveis
para qualquer intermediário da rede. Serve para validar o deploy; não para uso
real.

### A. Só IP, HTTP — o que você acabou de fazer

Nada mais a fazer. Continue apenas se estiver testando, com dados descartáveis.

### B. Domínio com TLS no próprio servidor (recomendado)

1. Registre um domínio e crie um registro **A** apontando para o IP do servidor.
   Espere a propagação (`dig +short seudominio.com` deve devolver seu IP).
2. No `.env`:

```ini
DOMAIN=seudominio.com
HTTP_PORT=127.0.0.1:8080
VITE_API_URL=https://seudominio.com
DJANGO_ALLOWED_HOSTS=seudominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://seudominio.com
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_AUTH_COOKIE_SECURE=True
```

3. Suba com a sobreposição de TLS:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.tls.yml up -d --build
```

O [Caddy](deploy/Caddyfile) obtém e renova o certificado Let's Encrypt sozinho —
sem cron e sem comando de renovação. `HTTP_PORT=127.0.0.1:8080` tira o nginx da
porta pública: ele passa a escutar só em loopback, alcançável apenas pelo Caddy.

Só ative o HSTS (`DJANGO_SECURE_HSTS_SECONDS=31536000`) **depois** de confirmar
que o certificado funciona. O navegador memoriza a exigência de HTTPS por um ano;
se algo estiver errado, você perde o acesso e não há como pedir para ele
esquecer.

> **Alternativa com Certbot:** se preferir terminar o TLS no próprio nginx, é
> possível — mas exige montar os certificados, adicionar um bloco `listen 443
> ssl` ao `frontend/nginx.conf` e agendar a renovação. Três coisas para manter
> em vez de nenhuma.

### C. Domínio atrás do Cloudflare

O Cloudflare termina o TLS na borda e conversa com seu servidor por HTTP.

1. Aponte os nameservers do domínio para o Cloudflare, com o registro **proxied**
   (nuvem laranja).
2. Em SSL/TLS, escolha o modo **Full**. *Flexible* deixa o trecho
   Cloudflare→servidor sem criptografia e provoca laço de redirecionamento com
   `SECURE_SSL_REDIRECT` ligado.
3. `.env` igual ao cenário B, exceto `HTTP_PORT=80` e sem o arquivo de TLS.
4. Opcional: restrinja o `ufw` às faixas de IP do Cloudflare, para ninguém
   alcançar o servidor direto pelo IP e contornar a borda.

O que faz isso funcionar já está no código: o nginx repassa `X-Forwarded-Proto` e
o `settings.py` lê esse cabeçalho em `SECURE_PROXY_SSL_HEADER`. Sem isso, o Django
enxergaria HTTP, redirecionaria para HTTPS, e o Cloudflare devolveria a
requisição em HTTP — laço infinito.

---

## Operação

### Atualizar a aplicação

```bash
cd ~/freecash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

As migrations rodam sozinhas no entrypoint. **Se você mudou `VITE_API_URL`**, o
`--build` é obrigatório: o Vite embute essa variável no bundle em tempo de build,
então trocá-la sem reconstruir não tem efeito nenhum.

### Backup do banco

O volume `postgres_data_prod` sobrevive a `down` e `up`, mas **não** a
`docker compose down -v`, nem à perda do servidor. Backup é arquivo fora daqui:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U freecash_user freecash_db | gzip > ~/backup-$(date +%F).sql.gz
```

Diário, às 3h, guardando os últimos 7 dias (`crontab -e`):

```
0 3 * * * cd /home/deploy/freecash && docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U freecash_user freecash_db | gzip > /home/deploy/backups/db-$(date +\%F).sql.gz && find /home/deploy/backups -name 'db-*.sql.gz' -mtime +7 -delete
```

Crie a pasta antes (`mkdir -p ~/backups`) e **copie periodicamente para fora do
servidor** — backup que mora na máquina que pode se perder não é backup.

Restaurar:

```bash
gunzip -c backup-2026-01-15.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres psql -U freecash_user freecash_db
```

### Comandos do dia a dia

```bash
docker compose -f docker-compose.prod.yml ps                    # estado
docker compose -f docker-compose.prod.yml logs -f backend       # logs ao vivo
docker compose -f docker-compose.prod.yml restart backend       # reiniciar um serviço
docker compose -f docker-compose.prod.yml down                  # parar (preserva dados)
docker system prune -a                                          # liberar disco
```

`docker compose down -v` apaga o volume do banco. É o comando que destrói os
dados; não o use no servidor sem backup na mão.

### Quando algo dá errado

| Sintoma | Causa provável |
|---|---|
| Backend reinicia em laço | `validar_config_producao()` recusou o `.env`. O log diz qual variável falta. |
| `DisallowedHost` no log | O IP ou domínio usado não está em `DJANGO_ALLOWED_HOSTS`. |
| Tela branca, `/api/` com 404 | Frontend construído com `VITE_API_URL` errada. Corrija o `.env` e refaça o build. |
| 502 no nginx | Backend ainda subindo ou caído: `logs backend`. |
| Build do frontend morre sem erro claro | Memória insuficiente. Adicione swap ou use uma máquina de 2 GB. |
| Login funciona e "cai" ao recarregar | Cookie com `Secure` em conexão HTTP. Em HTTP puro, `DJANGO_AUTH_COOKIE_SECURE=False`. |

Swap de 2 GB, se precisar:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Ensaio antes de ir para o VPS

Vale rodar o compose de produção na sua máquina primeiro — mesma imagem, mesmos
passos, sem custo:

```bash
cp .env .env.dev.bak                      # guarde o .env de desenvolvimento
# edite o .env com DJANGO_DEBUG=False, uma SECRET_KEY real e
# DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
docker compose -f docker-compose.prod.yml up -d --build
curl http://localhost/api/health/
```

Acesse `http://localhost`, faça login, navegue. Se funcionar aqui, o que resta no
servidor é diferença de ambiente, não de aplicação. Depois:

```bash
docker compose -f docker-compose.prod.yml down
mv .env.dev.bak .env
```

---

## Depois: deploy automático

Quando o deploy manual estiver confortável, dá para o GitHub Actions publicar
sozinho a cada merge em `main`. O esqueleto:

1. Gere um par de chaves só para isso e coloque a pública em
   `~/.ssh/authorized_keys` do usuário `deploy`.
2. No repositório: **Settings** → **Secrets and variables** → **Actions**, crie
   `VPS_HOST`, `VPS_USER` e `VPS_SSH_KEY` (a chave **privada**).
3. Um job com `appleboy/ssh-action` executando `git pull && docker compose -f
   docker-compose.prod.yml up -d --build` no servidor.

Deixe para depois do primeiro deploy manual bem-sucedido: automatizar um
procedimento que você ainda não executou à mão transforma qualquer erro em erro
de duas camadas ao mesmo tempo.

---

## Referências no repositório

- [.env_example](.env_example) — todas as variáveis, com os três cenários
- [docker-compose.prod.yml](docker-compose.prod.yml) — a composição de produção
- [deploy/Caddyfile](deploy/Caddyfile) — proxy com TLS automático
- [frontend/nginx.conf](frontend/nginx.conf) — SPA, proxy da API e cabeçalhos
