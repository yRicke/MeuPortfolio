# Página de projeto

A primeira tela apresenta o nome, um resumo da descrição cadastrada e a ação
de acesso. O resumo usa a primeira frase; o texto completo continua na seção
Sobre o projeto, com parágrafos preservados. Não são gerados novos textos ou
alterados os dados cadastrados.

O destino é identificado pelo domínio. Links do GitHub usam a ação Ver no
GitHub; os demais usam Acessar projeto. Sem URL cadastrada, a página explica
a ausência e mantém a navegação pela descrição e pelas imagens.

O nome e as ações ficam fora dos slides. A galeria permite navegação manual,
teclado e gesto horizontal, preserva o enquadramento das imagens e oferece
Ampliar imagem para a imagem atual. Sem galeria, usa a capa como prévia.

No desktop, o bloco de acesso acompanha a leitura da descrição. No mobile,
um atalho inferior aparece quando o botão inicial deixa de estar totalmente
visível. Há espaço reservado no final para não encobrir os últimos links.
Sem JavaScript ou IntersectionObserver, os links da apresentação e do bloco
de informações continuam acessíveis.

O tema, a tipografia, os recortes das imagens e o carrossel manual foram
mantidos. A animação de entrada ocorre apenas na galeria; título, resumo e
ação ficam disponíveis imediatamente. A capa e o preloader não foram alterados.

Validação: testes Django da página, testes JavaScript da navegação e do
atalho de acesso, e verificação HTTP após o deploy. A conferência visual em
um navegador real deve cobrir desktop, telas de 320 a 430 px e nomes longos.
