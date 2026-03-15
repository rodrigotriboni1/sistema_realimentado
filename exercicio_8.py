import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import lfilter

# Coeficientes: b (numerador) e a (denominador) de H(z)
# H(z) = 1 / (1 - 0.5z^{-1} + 0.25z^{-2})
b = [1]
a = [1, -0.5, 0.25]

N = 50
n = np.arange(N)
u = np.ones(N)  # degrau unitário

y = lfilter(b, a, u)

plt.figure(figsize=(8, 4))
plt.stem(n, y, basefmt='k-')
plt.title('Resposta ao Degrau do Sistema')
plt.xlabel('n')
plt.ylabel('y[n]')
plt.grid(True)
plt.tight_layout()
plt.savefig('resposta_degrau.png', dpi=150)
plt.show()
print(f"Valor final (regime permanente): {y[-1]:.4f}")
print(f"Valor teórico H(1) = 1/(1 - 0.5 + 0.25) = {1/(1 - 0.5 + 0.25):.4f}")