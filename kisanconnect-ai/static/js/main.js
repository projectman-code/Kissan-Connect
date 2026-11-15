/* KisanConnect AI front-end behaviour. No build step, no dependencies. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var LANG = document.documentElement.lang || "en";

  function post(url, body, isForm) {
    var opts = { method: "POST", headers: { "X-CSRF-Token": csrf }, credentials: "same-origin" };
    if (isForm) { opts.body = body; }
    else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    return fetch(url, opts).then(function (r) { return r.json().then(function (j) { j._status = r.status; return j; }); });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /* ---- mobile nav */
  var toggle = $("[data-nav-toggle]");
  if (toggle) toggle.addEventListener("click", function () {
    var open = $("#nav").classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  /* ---- toasts fade out */
  $$(".toast").forEach(function (t, i) {
    setTimeout(function () { t.classList.add("out"); setTimeout(function () { t.remove(); }, 400); }, 4500 + i * 600);
  });

  /* ---- auto-submit filters */
  $$("[data-autosubmit]").forEach(function (f) {
    f.addEventListener("change", function () { if (f.form) f.form.submit(); });
  });

  /* ---- quantity steppers */
  $$("[data-qty]").forEach(function (box) {
    var input = $("input", box), max = parseInt(box.dataset.max || "9999", 10);
    $$("[data-step]", box).forEach(function (b) {
      b.addEventListener("click", function () {
        var min = parseInt(input.min || "0", 10);
        var v = (parseInt(input.value, 10) || 0) + parseInt(b.dataset.step, 10);
        input.value = Math.max(min, Math.min(max, v));
      });
    });
  });

  /* ---- demo account buttons */
  $$(".demo-fill").forEach(function (b) {
    b.addEventListener("click", function () {
      $("#username").value = b.dataset.user;
      $("#password").value = b.dataset.pass;
      $("#password").focus();
    });
  });

  /* ---- image preview */
  $$("input[type=file][data-preview]").forEach(function (inp) {
    inp.addEventListener("change", function () {
      var img = $(inp.dataset.preview);
      var f = inp.files && inp.files[0];
      if (!f || !img) return;
      img.src = URL.createObjectURL(f);
      img.hidden = false;
    });
  });

  /* ---- farming assistant */
  var bot = $("#bot");
  if (bot) {
    var fab = $("[data-bot-open]"), log = $("[data-bot-log]", bot), chips = $("[data-bot-chips]", bot);
    var form = $("[data-bot-form]", bot), input = $("[data-bot-input]", bot);
    var started = false;
    function say(text, mine) {
      var b = el("div", "bubble" + (mine ? " mine" : ""), text);
      log.appendChild(b); log.scrollTop = log.scrollHeight;
    }
    function showChips(list) {
      chips.textContent = "";
      (list || []).forEach(function (s) {
        var b = el("button", "", s); b.type = "button";
        b.addEventListener("click", function () { ask(s); });
        chips.appendChild(b);
      });
    }
    function ask(text) {
      text = (text || "").trim(); if (!text) return;
      say(text, true); input.value = "";
      post("/api/ai/chat", { message: text }).then(function (r) {
        say(r.reply || "Sorry, I could not answer that right now.");
        showChips(r.suggestions);
      }).catch(function () { say("The assistant could not be reached. Check your connection and try again."); });
    }
    function open() {
      bot.hidden = false; fab.setAttribute("aria-expanded", "true"); input.focus();
      if (!started) { started = true; ask("hello"); log.firstChild && log.removeChild(log.firstChild); }
    }
    function close() { bot.hidden = true; fab.setAttribute("aria-expanded", "false"); fab.focus(); }
    fab.addEventListener("click", function () { bot.hidden ? open() : close(); });
    $("[data-bot-close]", bot).addEventListener("click", close);
    bot.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
    form.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
  }

  /* ---- farmer product form: AI price + AI grade */
  var pf = $("[data-product-form]");
  if (pf) {
    var crop = $("[data-crop]", pf), unit = $("[data-unit]", pf), other = $("[data-other]", pf);
    var grade = $("[data-grade]", pf), organic = $("[data-organic]", pf);
    var priceBox = $("[data-price-box]", pf), gradeBox = $("[data-grade-box]", pf);
    var priceIn = $("[data-price]", pf), file = $("[data-grade-input]", pf);

    crop.addEventListener("change", function () {
      other.hidden = crop.value !== "__other";
      var opt = crop.options[crop.selectedIndex];
      if (opt && opt.dataset.unit) unit.value = opt.dataset.unit;
    });

    $("[data-suggest]", pf).addEventListener("click", function () {
      priceBox.hidden = false; priceBox.textContent = "";
      if (!crop.value || crop.value === "__other") {
        priceBox.appendChild(el("p", "", "Choose a crop from the list first. Suggestions cover the listed crops."));
        return;
      }
      priceBox.appendChild(el("p", "", "Checking today's fair price..."));
      post("/api/ai/price", { crop: crop.value, grade: grade.value, organic: organic.checked }).then(function (r) {
        priceBox.textContent = "";
        if (r.error) { priceBox.appendChild(el("p", "", r.error)); return; }
        priceBox.appendChild(el("p", "", "Fair price for grade " + r.grade + (r.organic ? " organic " : " ") + r.crop + " in " + r.month));
        priceBox.appendChild(el("strong", "", "₹" + r.suggested + " per " + r.unit));
        priceBox.appendChild(el("p", "muted", "Likely range ₹" + r.low + " to ₹" + r.high + ". " + r.trend));
        var use = el("button", "btn btn-primary btn-sm", "Use ₹" + r.suggested); use.type = "button";
        use.addEventListener("click", function () { priceIn.value = r.suggested; priceIn.focus(); });
        priceBox.appendChild(use);
      }).catch(function () { priceBox.textContent = "Could not reach the price model. Try again."; });
    });

    if (file) file.addEventListener("change", function () {
      var f = file.files && file.files[0]; if (!f) return;
      gradeBox.textContent = ""; gradeBox.appendChild(el("p", "", "Grading your photo..."));
      var fd = new FormData(); fd.append("image", f);
      post("/api/ai/grade", fd, true).then(function (r) {
        gradeBox.textContent = "";
        if (r.error) { gradeBox.appendChild(el("p", "", r.error)); return; }
        grade.value = r.grade;
        gradeBox.appendChild(el("strong", "", "Grade " + r.grade + ", score " + r.score + "/100"));
        var d = r.details, rows = el("div", "mini-bars");
        [["Colour", d.colour], ["Brightness", d.brightness], ["Sharpness", d.sharpness], ["Even colour", d.uniformity], ["Free of blemishes", d.blemish_free]]
          .forEach(function (x) { rows.appendChild(el("span", "", x[0] + ": " + x[1] + "%")); });
        gradeBox.appendChild(rows);
        r.tips.forEach(function (t) { gradeBox.appendChild(el("p", "muted small", t)); });
      }).catch(function () { gradeBox.textContent = "Could not grade the photo. You can still pick a grade yourself."; });
    });
  }

  /* ---- chat polling */
  var cl = $("[data-chat-log]");
  if (cl) {
    var uid = cl.dataset.uid, pid = cl.dataset.product || null, last = 0, mine = 0;
    var cform = $("[data-chat-form]"), cin = $("[data-chat-input]");
    function render(msgs) {
      msgs.forEach(function (m) {
        last = Math.max(last, m.id);
        var b = el("div", "bubble" + (m.mine ? " mine" : ""), m.body);
        b.appendChild(el("small", "", (m.created_at || "").slice(11, 16)));
        cl.appendChild(b);
      });
      if (msgs.length) cl.scrollTop = cl.scrollHeight;
    }
    function poll() {
      fetch("/api/chat/" + uid + "?after=" + last, { credentials: "same-origin" })
        .then(function (r) { return r.json(); }).then(function (j) { if (j.messages) render(j.messages); }).catch(function () {});
    }
    poll();
    var timer = setInterval(function () { if (!document.hidden) poll(); }, 4000);
    cform.addEventListener("submit", function (e) {
      e.preventDefault();
      var body = cin.value.trim(); if (!body) return;
      cin.value = "";
      post("/api/chat/" + uid + "?after=" + last, { body: body, product_id: pid }).then(function (j) {
        if (j.messages) render(j.messages);
        else if (j.error) { cin.value = body; }
      });
    });
  }
})();
