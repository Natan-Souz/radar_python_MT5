## 🧠 Conceito Central

O projeto parte da premissa de que:

> _Nem todos os ativos merecem atenção ao mesmo tempo._

Portanto, o sistema busca responder continuamente à pergunta:

> **“Quais ativos fazem mais sentido observar agora?”**

Para isso, o radar avalia cada ativo sob múltiplos pilares, gera uma **pontuação comparável** e constrói um **ranking balanceado**.

---

## 🧩 Principais Pilares de Análise

O radar é **agnóstico de estratégia de entrada**. Ele avalia contexto e qualidade do ativo, não sinais de trade.

Os pilares atuais incluem:

- **Liquidez**
    
    - Volume financeiro
        
    - Atividade recente
        
- **Volatilidade**
    
    - ATR e métricas derivadas
        
    - Adequação a movimentos intraday
        
- **Tendência / Contexto**
    
    - Indicadores direcionais (ex.: ADX)
        
    - Estrutura de mercado
        
- **Atividade intraday**
    
    - Intensidade de movimento
        
    - Potencial operacional
        

Cada pilar contribui para uma **pontuação final**, utilizada para ranqueamento.

---

## ⚖️ Balanceamento por Classe de Ativo

Um dos diferenciais do projeto é o **balanceamento do Top N por classe de ativo**, evitando vieses como:

- Todos os ativos serem Forex
    
- Excesso de cripto em momentos específicos
    
- Falta de diversificação estrutural
    

As classes atualmente suportadas incluem, por exemplo:

- Forex
    
- Índices
    
- Ações
    
- Criptomoedas
    
- Commodities
    
- ETFs

- Futuros
    

O sistema distribui as vagas do ranking de forma proporcional entre as classes selecionadas.

---

## 🏗️ Arquitetura Geral

O projeto foi desenvolvido de forma **modular**, facilitando manutenção, testes e evolução.

Estrutura simplificada:

`python_radar/ 
├── scanner/                  # Orquestração do scan 
    ├── indicators.py         # Cálculo de indicadores técnicos 
    ├── regime_detector.py    # Classificação de regime de mercado 
    ├── scorer.py             # Sistema de pontuação 
    ├── balancing.py          # Balanceamento por classe de ativo 
    ├── universe.py           # Universo de ativos analisáveis 
    ├── data_feed.py          # Coleta de dados (MetaTrader 5) 
    ├── storage.py            # Persistência (ex.: SQLite) 
    ├── logger.py             # Logs estruturados 
    ├── config.py             # Configurações gerais 
    ├── radar.py              # Criação de dicionário
    ├── strategy_mapper.py    # Mapeamento das estratégias
    └── main.py               # Ponto de entrada`

---

## 🔌 Integração com MetaTrader 5 (MT5)

O radar utiliza o **MetaTrader 5** como fonte de dados de mercado.

Requisitos:

- MetaTrader 5 instalado
    
- Terminal aberto e logado
    
- Ativos visíveis no _Market Watch_
    
- Permissão para uso da API Python do MT5
    

O projeto **não executa ordens**. Ele apenas consome dados e gera rankings.

---

## 🚀 Como Executar

### 1️⃣ Criar ambiente virtual

`python -m venv 
.venv source .venv/bin/activate # Linux/Mac 
.venv\Scripts\activate          # Windows`

### 2️⃣ Instalar dependências

`pip install -r requirements.txt`

### 3️⃣ Executar o radar

`python -m scanner.main`

Os resultados são armazenados conforme a configuração do projeto (ex.: banco SQLite, logs).

---

## 📊 Saídas do Sistema

O radar gera, entre outros artefatos:

- Ranking de ativos observáveis
    
- Pontuações detalhadas por pilar
    
- Classificação de regime de mercado
    
- Logs estruturados para auditoria e debug
    

Essas saídas são pensadas para **alimentar outros módulos**, como:

- Robôs de trade
    
- Sistemas de alerta
    
- Dashboards
    
- Análises exploratórias
    

---

## 🔮 Evoluções Planejadas

Algumas extensões previstas ou possíveis:

- Análise multi-timeframe (contexto + intraday)
    
- Classificação explícita de regime (tendência, consolidação, choppy)
    
- Sugestão de tipo de estratégia por ativo (trend-follow, breakout, ignorar)
    
- Execução contínua (scanner em loop)
    
- Integração direta com Expert Advisors no MT5
    

---

## ⚠️ Aviso Importante

Este projeto tem **finalidade educacional e de pesquisa**.

Ele **não constitui recomendação de investimento**, nem substitui análise profissional.  
Qualquer uso em ambiente real deve ser feito com cautela e responsabilidade.