import html
import json

import folium
import pandas as pd
from branca.element import MacroElement
from folium.plugins import HeatMap
from jinja2 import Template

CENTRO_MAPA = [-30.0346, -51.2177]
ZOOM_MAPA = 12
LIMITES_LATITUDE = (-30.30, -29.90)
LIMITES_LONGITUDE = (-51.30, -51.00)

COR_GRAVE = "#d73027"
COR_DEMAIS = "#2b6cb0"

NOTA_AGRUPAMENTO = (
    "Itens do mesmo tipo e próximos viram um ponto com o número de itens. "
    "Aproxime o zoom para separá-los."
)

# Cor e formato de cada grupo de sinalização. Os dois juntos ajudam a
# diferenciar os grupos mesmo com muitos pontos sobrepostos.
ESTILO_SINALIZACAO = {
    "Travessia de pedestres": ("#2ca25f", "triangulo"),
    "Pare / retenção": ("#f28e2b", "octogono"),
    "Transporte coletivo": ("#7b3294", "quadrado"),
    "Velocidade e moderadores": ("#c9a400", "losango"),
    "Estacionamento": ("#17a2b8", "circulo"),
    "Divisão de pista e delimitação": ("#4d4d4d", "cruz"),
    "Bicicletas": ("#e377c2", "triangulo_invertido"),
    "Setas e orientação": ("#8c564b", "hexagono"),
    "Outras placas e marcações": ("#9e9e9e", "x"),
}


# O Leaflet só desenha círculos prontos. Para ter formatos diferentes e
# agrupar sinais por zoom, a sinalização é desenhada em um canvas próprio.
# Os pontos ficam em coordenadas de mundo (Mercator, de 0 a 1) e o agrupamento
# é feito em células de pixels do zoom atual, separadamente por grupo.
SCRIPT_AGRUPADA = """
{% macro script(this, kwargs) %}
(function () {
    var mapa = {{ this._parent.get_name() }};
    var D = {{ this.dados }};
    var N = D.lat.length;
    var NC = D.cats.length;
    var TAMANHO_CELULA = 44;

    var wx = new Float64Array(N), wy = new Float64Array(N);
    var cat = new Int8Array(N);
    for (var i = 0; i < N; i++) {
        var lat = D.lat[i] * Math.PI / 180;
        wx[i] = (D.lon[i] + 180) / 360;
        wy[i] = (1 - Math.log(Math.tan(lat) + 1 / Math.cos(lat)) / Math.PI) / 2;
        cat[i] = D.cat[i];
    }
    var unitarios = new Uint32Array(N).fill(1);
    var individuais = { x: wx, y: wy, cat: cat, n: unitarios, ids: null };
    var visivel = [];
    for (var v = 0; v < NC; v++) { visivel.push(true); }
    var agrupar = true;
    var destaque = -1;   // tipo sob o mouse no painel: é desenhado por cima de todos
    var cache = {};
    var ativo = {{ "true" if this.ativo else "false" }};

    // ---------- formatos ----------
    var CRUZ = [[-0.38,-1],[0.38,-1],[0.38,-0.38],[1,-0.38],[1,0.38],[0.38,0.38],
                [0.38,1],[-0.38,1],[-0.38,0.38],[-1,0.38],[-1,-0.38],[-0.38,-0.38]];
    var POLIGONOS = {
        triangulo: [[0,-1.25],[1.1,0.9],[-1.1,0.9]],
        triangulo_invertido: [[0,1.25],[1.1,-0.9],[-1.1,-0.9]],
        losango: [[0,-1.35],[1.35,0],[0,1.35],[-1.35,0]],
        cruz: CRUZ.map(function (p) { return [p[0] * 1.15, p[1] * 1.15]; }),
        x: CRUZ.map(function (p) {
            var c = Math.SQRT1_2;
            return [(p[0] - p[1]) * c * 1.15, (p[0] + p[1]) * c * 1.15];
        })
    };
    function regular(lados, rotacao) {
        var pts = [];
        for (var k = 0; k < lados; k++) {
            var a = rotacao + k * 2 * Math.PI / lados - Math.PI / 2;
            pts.push([Math.cos(a) * 1.15, Math.sin(a) * 1.15]);
        }
        return pts;
    }
    POLIGONOS.hexagono = regular(6, 0);
    POLIGONOS.octogono = regular(8, Math.PI / 8);

    function tracar(ctx, forma, x, y, r) {
        if (forma === "circulo") {
            ctx.moveTo(x + r, y);
            ctx.arc(x, y, r, 0, 6.283185307);
        } else if (forma === "quadrado") {
            ctx.rect(x - r * 0.9, y - r * 0.9, r * 1.8, r * 1.8);
        } else {
            var pts = POLIGONOS[forma];
            ctx.moveTo(x + pts[0][0] * r, y + pts[0][1] * r);
            for (var k = 1; k < pts.length; k++) {
                ctx.lineTo(x + pts[k][0] * r, y + pts[k][1] * r);
            }
            ctx.closePath();
        }
    }

    // ---------- agrupamento por zoom ----------
    function agrupamento(z) {
        if (cache[z]) { return cache[z]; }
        var escala = 256 * Math.pow(2, z);
        var chaves = new Map();
        var ids = new Int32Array(N);
        var gc = [], gn = [], gx = [], gy = [];
        for (var i = 0; i < N; i++) {
            var cx = Math.floor(wx[i] * escala / TAMANHO_CELULA);
            var cy = Math.floor(wy[i] * escala / TAMANHO_CELULA);
            var chave = (cat[i] * 4194304 + cx) * 4194304 + cy;
            var id = chaves.get(chave);
            if (id === undefined) {
                id = gn.length;
                chaves.set(chave, id);
                gc.push(cat[i]); gn.push(0); gx.push(0); gy.push(0);
            }
            ids[i] = id;
            gn[id] += 1; gx[id] += wx[i]; gy[id] += wy[i];
        }
        var M = gn.length;
        var x = new Float64Array(M), y = new Float64Array(M);
        for (var g = 0; g < M; g++) { x[g] = gx[g] / gn[g]; y[g] = gy[g] / gn[g]; }
        cache[z] = { x: x, y: y, cat: Int8Array.from(gc), n: Uint32Array.from(gn), ids: ids };
        return cache[z];
    }

    // ---------- canvas ----------
    // O canvas fica numa camada própria do Leaflet, abaixo da camada das
    // dicas (z-index 650), para a dica sempre aparecer por cima dos pontos.
    var camadaSinais = mapa.createPane("agrupada-" + D.id);
    camadaSinais.style.zIndex = 450;
    camadaSinais.style.pointerEvents = "none";
    var canvas = document.createElement("canvas");
    canvas.style.cssText = "position:absolute;top:0;left:0;pointer-events:none;";
    camadaSinais.appendChild(canvas);
    canvas.style.display = ativo ? "" : "none";
    // As camadas se movem junto com o mapa; o canvas acompanha o contrário,
    // para continuar cobrindo exatamente a área visível.
    function posicionar() {
        L.DomUtil.setPosition(canvas, mapa.containerPointToLayerPoint([0, 0]));
    }

    var fonteAtual = individuais;
    var hx = [], hy = [], hr = [], hk = [];
    var pendente = false;
    var zoomando = false;
    var desenhos = 0;
    function depurar() {
        return { agrupar: agrupar, desenhados: hx.length, itens: fonteAtual.x.length,
                 total: N, zoom: mapa.getZoom(), desenhos: desenhos, zoomando: zoomando, ativo: ativo,
                 opacidade: canvas.style.opacity, destaque: destaque,
                 topoTipo: hk.length ? fonteAtual.cat[hk[hk.length - 1]] : -1 };
    }

    function rotulo(n) {
        return n < 1000 ? String(n) : (n / 1000).toFixed(1).replace(".", ",") + "k";
    }

    function desenhar() {
        pendente = false;
        desenhos += 1;
        posicionar();
        var tam = mapa.getSize();
        var dpr = window.devicePixelRatio || 1;
        var largura = Math.round(tam.x * dpr), altura = Math.round(tam.y * dpr);
        if (canvas.width !== largura || canvas.height !== altura) {
            canvas.width = largura; canvas.height = altura;
            canvas.style.width = tam.x + "px"; canvas.style.height = tam.y + "px";
        }
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, tam.x, tam.y);

        var zoom = mapa.getZoom();
        var fonte = agrupar ? agrupamento(Math.round(zoom)) : individuais;
        fonteAtual = fonte;
        var escala = 256 * Math.pow(2, zoom);
        var origem = mapa.getPixelBounds().min;
        var fracao = Math.min(1, Math.max(0, (zoom - 11) / 6));
        var base = 3 + 3.5 * fracao;
        var margem = 40;
        var total = fonte.x.length;

        // 1) itens visíveis na tela (tipo ligado e dentro da área do mapa),
        //    já separados por tipo
        var porTipo = [];
        for (var c0 = 0; c0 < NC; c0++) { porTipo.push([]); }
        var vx = new Float32Array(total), vy = new Float32Array(total), vr = new Float32Array(total);
        var nVis = 0;
        for (var k = 0; k < total; k++) {
            var ck = fonte.cat[k];
            if (!visivel[ck]) { continue; }
            var sx = fonte.x[k] * escala - origem.x;
            var sy = fonte.y[k] * escala - origem.y;
            if (sx < -margem || sy < -margem || sx > tam.x + margem || sy > tam.y + margem) { continue; }
            var n = fonte.n[k];
            vx[k] = sx; vy[k] = sy;
            vr[k] = n > 1 ? base + Math.min(10, 2.6 * Math.log2(n)) : base * (D.cats[ck].escala || 1);
            porTipo[ck].push(k);
            nVis += 1;
        }

        // 2) desenho. Com poucos itens, um por um e dos maiores para os
        //    menores (os menores ficam por cima e continuam visíveis). Com
        //    muitos itens, um único traçado por tipo, que é bem mais rápido.
        hx = []; hy = []; hr = []; hk = [];
        var ordem = [];
        for (var c1 = 0; c1 < NC; c1++) { ordem = ordem.concat(porTipo[c1]); }
        if (agrupar) {
            ordem.sort(function (a, b) { return fonte.n[b] - fonte.n[a]; });
        }
        if (destaque >= 0) {
            var normais = [], realcados = [];
            for (var r = 0; r < ordem.length; r++) {
                (fonte.cat[ordem[r]] === destaque ? realcados : normais).push(ordem[r]);
            }
            ordem = normais.concat(realcados);
        }
        var ordemTipos = [];
        for (var ot = 0; ot < NC; ot++) { if (ot !== destaque) { ordemTipos.push(ot); } }
        if (destaque >= 0) { ordemTipos.push(destaque); }
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(255,255,255,0.9)";

        if (nVis <= 6000) {
            for (var o = 0; o < ordem.length; o++) {
                var q = ordem[o], cfgq = D.cats[fonte.cat[q]];
                ctx.beginPath();
                tracar(ctx, cfgq.forma, vx[q], vy[q], vr[q]);
                ctx.globalAlpha = fonte.n[q] > 1 ? 0.85 : (cfgq.alfa || 0.8);
                ctx.fillStyle = cfgq.cor; ctx.fill();
                ctx.globalAlpha = 0.9; ctx.stroke();
                hx.push(vx[q]); hy.push(vy[q]); hr.push(vr[q]); hk.push(q);
            }
        } else {
            // Acima de 20 mil itens na tela os formatos têm poucos pixels e
            // não dá para distingui-los; quadradinhos coloridos são bem mais
            // rápidos de desenhar.
            var simples = nVis > 20000;
            for (var ci = 0; ci < ordemTipos.length; ci++) {
                var c = ordemTipos[ci];
                var lista = porTipo[c];
                if (lista.length === 0) { continue; }
                ctx.globalAlpha = D.cats[c].alfa || 0.8;
                ctx.fillStyle = D.cats[c].cor;
                if (!simples) { ctx.beginPath(); }
                for (var o2 = 0; o2 < lista.length; o2++) {
                    var q2 = lista[o2];
                    if (simples) {
                        ctx.fillRect(vx[q2] - vr[q2] * 0.8, vy[q2] - vr[q2] * 0.8, vr[q2] * 1.6, vr[q2] * 1.6);
                    } else {
                        tracar(ctx, D.cats[c].forma, vx[q2], vy[q2], vr[q2]);
                    }
                    hx.push(vx[q2]); hy.push(vy[q2]); hr.push(vr[q2]); hk.push(q2);
                }
                if (!simples) {
                    ctx.fill();
                    ctx.globalAlpha = 0.9;
                    ctx.stroke();
                }
            }
        }
        ctx.globalAlpha = 1;

        // 3) números dos grupos, dos maiores para os menores. Cada número vai
        //    numa etiqueta na cor do seu tipo (assim fica claro a qual tipo ele
        //    pertence quando grupos de tipos diferentes se sobrepõem). Se uma
        //    etiqueta colidir com outra, ela desce ou sobe um pouco; se ainda
        //    colidir, é omitida.
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.lineJoin = "round";
        var caixas = [];
        var porTamanho = agrupar ? ordem.filter(function (q) { return fonte.n[q] > 1; }) : [];
        porTamanho.sort(function (a, b) { return fonte.n[b] - fonte.n[a]; });
        if (destaque >= 0) {
            porTamanho = porTamanho.filter(function (q) { return fonte.cat[q] === destaque; })
                .concat(porTamanho.filter(function (q) { return fonte.cat[q] !== destaque; }));
        }
        var deslocamentos = [0, 16, -16];
        for (var t = 0; t < porTamanho.length && caixas.length < 1500; t++) {
            var qq = porTamanho[t];
            var txt = rotulo(fonte.n[qq]);
            var meia = ctx.measureText(txt).width / 2 + 5;
            var yc = null;
            for (var d = 0; d < deslocamentos.length && yc === null; d++) {
                var ty = vy[qq] + deslocamentos[d];
                var colide = false;
                for (var b = 0; b < caixas.length; b++) {
                    var cb = caixas[b];
                    if (Math.abs(vx[qq] - cb[0]) < meia + cb[2] && Math.abs(ty - cb[1]) < 15) { colide = true; break; }
                }
                if (!colide) { yc = ty; }
            }
            if (yc === null) { continue; }
            caixas.push([vx[qq], yc, meia]);
            ctx.beginPath();
            ctx.rect(vx[qq] - meia, yc - 8, meia * 2, 16);
            ctx.fillStyle = D.cats[fonte.cat[qq]].cor;
            ctx.globalAlpha = 0.95;
            ctx.fill();
            ctx.globalAlpha = 1;
            ctx.lineWidth = 1;
            ctx.strokeStyle = "rgba(255,255,255,0.95)";
            ctx.stroke();
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = "rgba(0,0,0,0.55)";
            ctx.strokeText(txt, vx[qq], yc + 0.5);
            ctx.fillStyle = "#ffffff";
            ctx.fillText(txt, vx[qq], yc + 0.5);
        }
    }
    function agendar() {
        if (zoomando || !ativo) { return; }
        if (!pendente) { pendente = true; requestAnimationFrame(desenhar); }
    }

    // ---------- dica ao passar o mouse ----------
    // direção automática: abre para o lado em que há espaço, sem sair do mapa
    var dica = L.tooltip({ direction: "auto", offset: [12, 0], opacity: 0.97,
                           className: "dica-sinais" });
    var itemAtual = null;
    function descricaoDe(i) {
        if (D.modo === "acidentes") {
            return "<b>" + D.descr[D.d[i]] + "</b><br>" + D.datas[D.dt[i]] + " às " +
                D.horas[D.hh[i]] + "<br>" + D.ruas[D.rr[i]] + "<br>Feridos: " + D.fe[i] +
                " (graves: " + D.fg[i] + ") · Mortes: " + D.mo[i];
        }
        return D.descr[D.d[i]] + (D.ano[i] ? "<br>Implantada em " + D.ano[i] : "");
    }
    function conteudo(k) {
        var c = fonteAtual.cat[k], n = fonteAtual.n[k];
        var titulo = "<b>" + D.cats[c].nome + "</b>";
        if (fonteAtual.ids === null) { return titulo + "<br>" + descricaoDe(k); }
        var contagem = {}, ultimo = -1;
        for (var i = 0; i < N; i++) {
            if (fonteAtual.ids[i] === k) {
                contagem[D.d[i]] = (contagem[D.d[i]] || 0) + 1;
                ultimo = i;
            }
        }
        if (n === 1) { return titulo + "<br>" + descricaoDe(ultimo); }
        var pares = Object.keys(contagem).map(function (d) { return [d, contagem[d]]; });
        pares.sort(function (a, b) { return b[1] - a[1]; });
        var linhas = pares.slice(0, 6).map(function (p) {
            return D.descr[p[0]] + " <b>×" + p[1] + "</b>";
        });
        var extra = pares.length > 6 ? "<br>…e mais " + (pares.length - 6) + " " + D.rotulo_tipos : "";
        return titulo + " — <b>" + n.toLocaleString("pt-BR") + " " + D.unidade + "</b><br>" + linhas.join("<br>") + extra;
    }
    function fecharDica() {
        itemAtual = null;
        mapa.closeTooltip(dica);
        mapa.getContainer().style.cursor = "";
    }
    mapa.on("mousemove", function (e) {
        if (!ativo) { return; }
        var p = e.containerPoint, achado = -1;
        for (var j = hx.length - 1; j >= 0; j--) {
            var dx = hx[j] - p.x, dy = hy[j] - p.y, lim = hr[j] + 2;
            if (dx * dx + dy * dy <= lim * lim) { achado = j; break; }
        }
        if (achado === -1) {
            if (itemAtual !== null) { fecharDica(); }
            return;
        }
        var chave = hk[achado] + ":" + (agrupar ? 1 : 0) + ":" + Math.round(mapa.getZoom());
        if (chave !== itemAtual) {
            itemAtual = chave;
            dica.setContent(conteudo(hk[achado]));
        }
        dica.setLatLng(mapa.containerPointToLatLng(L.point(hx[achado], hy[achado])));
        mapa.openTooltip(dica);
        mapa.getContainer().style.cursor = "pointer";
    });
    mapa.on("movestart", fecharDica);

    // ---------- painel: tipos de sinalização e agrupamento ----------
    var painel = L.control({ position: "topright" });
    painel.onAdd = function () {
        var div = L.DomUtil.create("div", "painel-agrupada");
        div.style.cssText = "background:rgba(255,255,255,0.96);color:#222;padding:10px 12px;" +
            "border-radius:6px;box-shadow:0 1px 5px rgba(0,0,0,0.4);font:13px/1.5 sans-serif;" +
            "max-height:" + Math.max(200, mapa.getSize().y - 40) + "px;overflow:auto;";
        var titulo = L.DomUtil.create("div", "", div);
        titulo.style.cssText = "font-weight:700;margin-bottom:4px;";
        titulo.textContent = D.titulo;
        D.cats.forEach(function (cfg, c) {
            var linha = L.DomUtil.create("label", "", div);
            linha.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;" +
                "padding:1px 4px;margin:0 -4px;border-radius:4px;";
            linha.title = "Passe o mouse para trazer este tipo para a frente";
            linha.addEventListener("mouseenter", function () {
                destaque = c; linha.style.background = "#e9eef5"; agendar();
            });
            linha.addEventListener("mouseleave", function () {
                if (destaque === c) { destaque = -1; }
                linha.style.background = ""; agendar();
            });
            var caixa = L.DomUtil.create("input", "", linha);
            caixa.type = "checkbox"; caixa.checked = true;
            caixa.addEventListener("change", function () { visivel[c] = caixa.checked; agendar(); });
            var amostra = L.DomUtil.create("canvas", "", linha);
            amostra.width = 20; amostra.height = 20;
            var cx = amostra.getContext("2d");
            cx.beginPath(); tracar(cx, cfg.forma, 10, 10, 7);
            cx.fillStyle = cfg.cor; cx.fill();
            cx.lineWidth = 1; cx.strokeStyle = "#888"; cx.stroke();
            var texto = L.DomUtil.create("span", "", linha);
            texto.innerHTML = cfg.nome + " <b>(" + cfg.n.toLocaleString("pt-BR") + ")</b>";
            if (cfg.ajuda) {
                var ajuda = L.DomUtil.create("div", "", div);
                ajuda.style.cssText = "font-size:11px;color:#666;margin:-2px 0 3px 46px;";
                ajuda.textContent = cfg.ajuda;
            }
        });
        var sep = L.DomUtil.create("div", "", div);
        sep.style.cssText = "border-top:1px solid #ddd;margin:7px 0 6px;";
        var linhaG = L.DomUtil.create("label", "", div);
        linhaG.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:700;";
        var caixaG = L.DomUtil.create("input", "", linhaG);
        caixaG.type = "checkbox"; caixaG.checked = true;
        caixaG.addEventListener("change", function () { agrupar = caixaG.checked; fecharDica(); agendar(); });
        var textoG = L.DomUtil.create("span", "", linhaG);
        textoG.textContent = D.rotulo_agrupar;
        var nota = L.DomUtil.create("div", "", div);
        nota.style.cssText = "font-size:11px;color:#666;max-width:250px;margin-top:3px;line-height:1.35;";
        nota.textContent = D.nota;
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        return div;
    };
    painel.addTo(mapa);
    painel.getContainer().style.display = ativo ? "" : "none";

    // Usado pelo alternador de visualizações do mapa.
    window.camadasAgrupadas = window.camadasAgrupadas || {};
    window.camadasAgrupadas[D.id] = {
        depurar: depurar,
        mostrar: function () {
            ativo = true; zoomando = false;
            canvas.style.display = "";
            canvas.style.transition = "none";
            canvas.style.opacity = "1";
            painel.getContainer().style.display = "";
            desenhar();
        },
        ocultar: function () {
            ativo = false;
            destaque = -1;
            fecharDica();
            hx = []; hy = []; hr = []; hk = [];
            canvas.style.display = "none";
            painel.getContainer().style.display = "none";
        }
    };

    // Durante a animação de zoom os pontos ficariam parados enquanto o mapa
    // de fundo se move. Então eles somem quando o zoom começa e voltam,
    // já na posição certa, quando termina.
    mapa.on("zoomstart", function () {
        if (!ativo) { return; }
        zoomando = true;
        fecharDica();
        canvas.style.transition = "none";
        canvas.style.opacity = "0";
    });
    mapa.on("zoomend", function () {
        zoomando = false;
        if (!ativo) { return; }
        desenhar();
        requestAnimationFrame(function () {
            canvas.style.transition = "opacity 0.18s ease-out";
            canvas.style.opacity = "1";
        });
    });
    mapa.on("move", function () { posicionar(); agendar(); });
    mapa.on("resize", agendar);
    mapa.whenReady(agendar);
    agendar();
})();
{% endmacro %}
"""


class CamadaAgrupada(MacroElement):
    _template = Template(SCRIPT_AGRUPADA)

    def __init__(self, dados, ativo=True):
        super().__init__()
        self._name = "CamadaAgrupada"
        self.ativo = ativo
        self.dados = json.dumps(
            dados,
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("</", "<\\/")


# Alterna entre as visualizações dentro do próprio mapa, no navegador. Assim a
# troca não reexecuta o app nem recria o mapa (o que fazia a tela piscar e
# voltar ao início); a posição e o zoom se mantêm entre as visualizações.
SCRIPT_VISTAS = """
{% macro script(this, kwargs) %}
(function () {
    var mapa = {{ this._parent.get_name() }};
    var calor = {{ this.nome_calor }};
    var VISTAS = { "Pontos": "acidentes", "Mapa de calor": null, "Sinalização": "sinalizacao" };
    var atual = "Pontos";

    function camada(vista) {
        var id = VISTAS[vista];
        return id && window.camadasAgrupadas ? window.camadasAgrupadas[id] : null;
    }
    function sair(vista) {
        if (vista === "Mapa de calor") {
            if (calor) { mapa.removeLayer(calor); }
        } else if (camada(vista)) {
            camada(vista).ocultar();
        }
    }
    function entrar(vista) {
        if (vista === "Mapa de calor") {
            if (calor) { mapa.addLayer(calor); }
        } else if (camada(vista)) {
            camada(vista).mostrar();
        }
        mapa.getContainer().classList.toggle("fundo-colorido", vista === "Mapa de calor");
    }
    function ir(vista) {
        if (vista === atual) { return; }
        sair(atual);
        atual = vista;
        entrar(vista);
    }
    window.vistaAtual = function () { return atual; };

    var painel = L.control({ position: "topleft" });
    painel.onAdd = function () {
        var div = L.DomUtil.create("div", "painel-vistas");
        div.style.cssText = "background:rgba(255,255,255,0.96);color:#222;padding:8px 12px;" +
            "border-radius:6px;box-shadow:0 1px 5px rgba(0,0,0,0.4);font:13px/1.6 sans-serif;";
        var titulo = L.DomUtil.create("div", "", div);
        titulo.style.cssText = "font-weight:700;margin-bottom:2px;";
        titulo.textContent = "Visualização";
        Object.keys(VISTAS).forEach(function (nome) {
            var linha = L.DomUtil.create("label", "", div);
            linha.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;";
            var radio = L.DomUtil.create("input", "", linha);
            radio.type = "radio"; radio.name = "vista-mapa"; radio.checked = (nome === atual);
            radio.addEventListener("change", function () { if (radio.checked) { ir(nome); } });
            var texto = L.DomUtil.create("span", "", linha);
            texto.textContent = nome;
        });
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    painel.addTo(mapa);
})();
{% endmacro %}
"""


class AlternadorVistas(MacroElement):
    _template = Template(SCRIPT_VISTAS)

    def __init__(self, calor=None):
        super().__init__()
        self._name = "AlternadorVistas"
        self.nome_calor = calor.get_name() if calor is not None else "null"


def pontos_em_porto_alegre(df):
    dados = df.dropna(subset=["latitude", "longitude"])
    return dados[
        dados["latitude"].between(*LIMITES_LATITUDE)
        & dados["longitude"].between(*LIMITES_LONGITUDE)
    ]


def _base_mapa():
    mapa = folium.Map(
        location=CENTRO_MAPA,
        zoom_start=ZOOM_MAPA,
        tiles=None,
        prefer_canvas=True,
    )
    folium.TileLayer("OpenStreetMap", control=False).add_to(mapa)
    # Fundo em tons de cinza: as cores dos pontos se destacam melhor.
    mapa.get_root().header.add_child(folium.Element(
        "<style>.leaflet-tile-pane {"
        "filter: grayscale(1) brightness(1.08) contrast(0.85);}"
        ".fundo-colorido .leaflet-tile-pane {filter: none;}"
        ".dica-sinais {white-space: normal; width: max-content; max-width: 320px;"
        "box-shadow: 0 1px 6px rgba(0,0,0,0.45);}</style>"
    ))
    return mapa


def _dados_acidentes(acidentes):
    pontos = pontos_em_porto_alegre(acidentes)
    grave = pontos["acidente_grave"].astype(int)

    tipos, nomes_tipos = pd.factorize(
        pontos["tipo_acid"].astype("string").fillna("Tipo não informado")
    )
    datas, nomes_datas = pd.factorize(
        pontos["data"].dt.strftime("%d/%m/%Y").fillna("sem data")
    )
    horas, nomes_horas = pd.factorize(
        pontos["hora"].astype("string").str[:5].fillna("--:--")
    )
    ruas, nomes_ruas = pd.factorize(
        pontos["log1"].astype("string").fillna("Local não informado")
    )

    def inteiros(coluna):
        return pontos[coluna].fillna(0).astype(int).tolist()

    # Os "demais" vêm primeiro e os graves por último: ficam desenhados por
    # cima e, sendo maiores, continuam visíveis em meio aos demais.
    return {
        "id": "acidentes",
        "modo": "acidentes",
        "titulo": "Tipo de acidente",
        "unidade": "acidentes",
        "rotulo_tipos": "tipos",
        "rotulo_agrupar": "Agrupar acidentes próximos",
        "nota": NOTA_AGRUPAMENTO.replace("Itens", "Acidentes").replace(
            "de itens", "de acidentes"
        ),
        "lat": pontos["latitude"].round(5).tolist(),
        "lon": pontos["longitude"].round(5).tolist(),
        "cat": grave.tolist(),
        "d": tipos.tolist(),
        "dt": datas.tolist(),
        "hh": horas.tolist(),
        "rr": ruas.tolist(),
        "fe": inteiros("feridos"),
        "fg": inteiros("feridos_gr"),
        "mo": inteiros("mortes"),
        "cats": [
            {
                "nome": "Demais acidentes",
                "cor": COR_DEMAIS,
                "forma": "circulo",
                "n": int((grave == 0).sum()),
                "escala": 0.75,
                "alfa": 0.5,
            },
            {
                "nome": "Acidentes graves",
                "cor": COR_GRAVE,
                "forma": "circulo",
                "n": int((grave == 1).sum()),
                "escala": 1.3,
                "alfa": 0.9,
                "ajuda": "com feridos graves ou mortes",
            },
        ],
        "descr": [html.escape(str(n)) for n in nomes_tipos],
        "datas": [str(n) for n in nomes_datas],
        "horas": [str(n) for n in nomes_horas],
        "ruas": [html.escape(str(n)) for n in nomes_ruas],
    }


def _dados_sinalizacao(sinalizacao):
    sinais = pontos_em_porto_alegre(sinalizacao)
    contagens = sinais["categoria"].value_counts()
    ordem = list(contagens.index)
    codigos = sinais["categoria"].map({c: i for i, c in enumerate(ordem)})
    descricoes, nomes = pd.factorize(
        sinais["descricao"].astype("string").fillna("Sem descrição")
    )

    return {
        "id": "sinalizacao",
        "modo": "sinalizacao",
        "titulo": "Tipo de sinalização",
        "unidade": "sinais",
        "rotulo_tipos": "descrições",
        "rotulo_agrupar": "Agrupar sinais próximos",
        "nota": NOTA_AGRUPAMENTO.replace("Itens", "Sinais").replace(
            "de itens", "de sinais"
        ),
        "lat": sinais["latitude"].round(5).tolist(),
        "lon": sinais["longitude"].round(5).tolist(),
        "cat": codigos.astype(int).tolist(),
        "d": descricoes.tolist(),
        "ano": sinais["implantacao"].dt.year.fillna(0).astype(int).tolist(),
        "cats": [
            {
                "nome": html.escape(c),
                "cor": ESTILO_SINALIZACAO.get(c, ("#999999", "circulo"))[0],
                "forma": ESTILO_SINALIZACAO.get(c, ("#999999", "circulo"))[1],
                "n": int(contagens[c]),
            }
            for c in ordem
        ],
        "descr": [html.escape(str(n)) for n in nomes],
    }


def mapa_vistas(acidentes, sinalizacao):
    """Um único mapa com as três visualizações.

    A troca entre elas acontece no navegador (painel "Visualização" dentro do
    mapa), sem reexecutar o app: não há piscada e a posição é mantida.
    """
    mapa = _base_mapa()

    CamadaAgrupada(_dados_acidentes(acidentes), ativo=True).add_to(mapa)
    CamadaAgrupada(_dados_sinalizacao(sinalizacao), ativo=False).add_to(mapa)

    pontos = pontos_em_porto_alegre(acidentes)
    calor = None
    if not pontos.empty:
        calor = HeatMap(
            pontos[["latitude", "longitude"]].values.tolist(),
            radius=12,
            blur=18,
            min_opacity=0.4,
            show=False,
            control=False,
            name="Mapa de calor",
        ).add_to(mapa)

    AlternadorVistas(calor).add_to(mapa)
    return mapa


# Do grupo com menos sinais (claro) ao com mais sinais (escuro).
CORES_DENSIDADE = ["#fde725", "#5ec962", "#21918c", "#3b528b", "#440154"]


def mapa_graves_sinalizacao(graves, grupos, raio):
    """Acidentes graves coloridos pelo grupo de densidade de sinais no raio.

    `graves` traz as colunas da relação espacial (dist_sinal, n_sinais) e
    `grupos` é o rótulo do grupo de cada acidente, na mesma ordem.
    """
    mapa = _base_mapa()
    pontos = pontos_em_porto_alegre(graves)
    grupos = grupos.loc[pontos.index]
    ordem = list(grupos.cat.categories)
    cores = dict(zip(ordem, CORES_DENSIDADE[-len(ordem):]))

    camada = folium.FeatureGroup(name="Acidentes graves").add_to(mapa)
    # Os grupos com menos sinais ficam por cima: são os que mais interessam.
    for grupo in reversed(ordem):
        do_grupo = pontos[grupos == grupo]
        registros = zip(
            do_grupo["latitude"],
            do_grupo["longitude"],
            do_grupo["data"].dt.strftime("%d/%m/%Y").fillna("sem data"),
            do_grupo["log1"].astype("string").fillna("Local não informado"),
            do_grupo["tipo_acid"].astype("string").fillna("Tipo não informado"),
            do_grupo["n_sinais"],
            do_grupo["dist_sinal"],
        )
        for latitude, longitude, data, rua, tipo, quantidade, distancia in registros:
            folium.CircleMarker(
                location=[latitude, longitude],
                radius=4,
                color="#222222",
                weight=0.6,
                fill=True,
                fill_color=cores[grupo],
                fill_opacity=0.85,
                tooltip=(
                    f"<b>{html.escape(tipo)}</b><br>{data} · {html.escape(rua)}<br>"
                    f"{int(quantidade)} sinais em até {raio} m<br>"
                    f"Sinal mais próximo: {distancia:.0f} m"
                ),
            ).add_to(camada)

    itens = "".join(
        f'<div><span style="display:inline-block;width:12px;height:12px;'
        f'border-radius:50%;background:{cores[g]};border:1px solid #222;'
        f'margin-right:6px;vertical-align:middle"></span>{html.escape(g)}</div>'
        for g in ordem
    )
    mapa.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:24px;left:12px;z-index:9999;'
        "background:rgba(255,255,255,0.92);color:#262730;padding:8px 10px;"
        'border-radius:6px;font:12px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.4)">'
        f"<b>Sinais em até {raio} m</b>{itens}</div>"
    ))
    return mapa
