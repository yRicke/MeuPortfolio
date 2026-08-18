# API de projetos e MCP

O portfólio expõe a mesma camada de gerenciamento por uma API REST versionada e
por um servidor MCP remoto. As duas interfaces usam uma única chave Bearer,
rotacionável por usuários `is_staff`.

## Ativação e rotação da chave

1. Fora da Vercel, execute as migrações com `python manage.py migrate`.
2. Entre no site com uma conta staff.
3. Acesse `/painel/api/` e selecione **Gerar primeira chave**.
4. Copie o valor exibido. A aplicação armazena apenas o hash, então a chave não
   poderá ser consultada novamente.

Ao selecionar **Trocar chave**, a chave anterior perde o acesso imediatamente.
Atualize os clientes que usam a credencial logo após a rotação.

Na Vercel, o `buildCommand` versionado em `vercel.json` executa
`python manage.py migrate --noinput` antes de ativar cada novo deployment. A
variável `DATABASE_URL` precisa estar disponível no ambiente correspondente; se
uma migration falhar, o build também falha e o artefato incompleto não é
publicado.

## Conectar ao Codex por MCP

O endpoint MCP usa Streamable HTTP em `https://SEU-DOMINIO/mcp/`. Defina a chave
no ambiente que inicia o Codex:

```powershell
$env:PORTFOLIO_API_TOKEN="portfolio_sua_chave"
```

Copie o conteúdo de `.codex/config.toml.example` para `.codex/config.toml` e
troque `SEU-DOMINIO` pelo host implantado. O arquivo de exemplo configura o token
por variável de ambiente e solicita aprovação para ferramentas de escrita.

Depois de reiniciar o Codex, o servidor disponibiliza estas ferramentas:

- `listar_projetos` e `obter_projeto`;
- `criar_projeto`, `atualizar_projeto` e `excluir_projeto`;
- `adicionar_imagens_projeto` e `excluir_imagem_projeto`;
- `organizar_projetos` e `organizar_imagens_projeto`.

Nas ferramentas MCP, arquivos são objetos com `nome` e `conteudo_base64`. PNG,
JPEG e WebP são aceitos, com limite de 10 MB por imagem.

## API REST v1

Todas as requisições exigem o cabeçalho:

```http
Authorization: Bearer portfolio_sua_chave
```

| Método | Rota | Operação |
| --- | --- | --- |
| `GET` | `/api/v1/` | Metadados e URLs da API |
| `GET`, `POST` | `/api/v1/projetos/` | Listar ou criar projetos |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/v1/projetos/{id}/` | Consultar, substituir, editar ou excluir |
| `PATCH` | `/api/v1/projetos/organizacao/` | Alterar a ordem completa e o destaque |
| `POST` | `/api/v1/projetos/{id}/imagens/` | Adicionar imagens à galeria |
| `PATCH` | `/api/v1/projetos/{id}/imagens/ordem/` | Alterar a ordem completa da galeria |
| `DELETE` | `/api/v1/projetos/{id}/imagens/{imagem_id}/` | Excluir uma imagem |

Criação em JSON sem arquivos:

```powershell
$headers = @{ Authorization = "Bearer $env:PORTFOLIO_API_TOKEN" }
$body = @{
  titulo = "Novo projeto"
  descricao = "Descrição do projeto"
  url = "https://example.com"
  data_desenvolvimento = "2026-08"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "https://SEU-DOMINIO/api/v1/projetos/" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Para JSON com imagem, acrescente `capa` e/ou `imagens`:

```json
{
  "titulo": "Novo projeto",
  "descricao": "Descrição",
  "capa": {
    "nome": "capa.png",
    "conteudo_base64": "iVBORw0KGgo..."
  },
  "imagens": [
    {
      "nome": "tela-1.jpg",
      "conteudo_base64": "/9j/4AAQSk..."
    }
  ]
}
```

Clientes REST também podem usar `multipart/form-data`: envie `capa` uma vez e
`imagens` repetidamente. `PATCH` altera somente os campos informados; `PUT` exige
ao menos `titulo` e `descricao`.

Os endpoints de organização exigem a lista completa e atual de IDs, sem
repetições. Isso evita ordens parciais ou inconsistentes quando outro cliente já
alterou o catálogo.
